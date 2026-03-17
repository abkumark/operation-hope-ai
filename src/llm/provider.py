"""LLM provider abstraction layer. Supports Azure OpenAI, OpenAI, and Ollama.

Includes retry logic with exponential backoff, basic token tracking,
and model version metadata for auditability.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from openai import AzureOpenAI, OpenAI

from config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token / cost tracking
# ---------------------------------------------------------------------------

@dataclass
class LLMCallRecord:
    """Record of a single LLM API call for tracking and auditability."""
    timestamp: datetime
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    success: bool
    error: str = ""


class TokenTracker:
    """Lightweight in-memory token usage tracker."""

    def __init__(self) -> None:
        self._records: list[LLMCallRecord] = []

    def record(self, rec: LLMCallRecord) -> None:
        self._records.append(rec)
        if rec.success:
            logger.debug(
                "LLM call: provider=%s model=%s tokens=%d latency=%.0fms",
                rec.provider, rec.model, rec.total_tokens, rec.latency_ms,
            )
        else:
            logger.warning(
                "LLM call FAILED: provider=%s model=%s error=%s latency=%.0fms",
                rec.provider, rec.model, rec.error, rec.latency_ms,
            )

    def get_summary(self) -> dict:
        total_calls = len(self._records)
        successful = [r for r in self._records if r.success]
        failed = total_calls - len(successful)
        total_tokens = sum(r.total_tokens for r in successful)
        return {
            "total_calls": total_calls,
            "successful_calls": len(successful),
            "failed_calls": failed,
            "total_tokens": total_tokens,
            "avg_tokens_per_call": total_tokens / len(successful) if successful else 0,
            "avg_latency_ms": (
                sum(r.latency_ms for r in successful) / len(successful)
                if successful else 0
            ),
        }

    def get_recent(self, n: int = 20) -> list[dict]:
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "provider": r.provider,
                "model": r.model,
                "total_tokens": r.total_tokens,
                "latency_ms": round(r.latency_ms, 1),
                "success": r.success,
                "error": r.error,
            }
            for r in self._records[-n:]
        ]


_token_tracker = TokenTracker()


def get_token_tracker() -> TokenTracker:
    return _token_tracker


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_DELAY_S = 1.0


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is retryable (transient API errors)."""
    exc_str = str(exc).lower()
    # OpenAI SDK wraps status codes in exception messages
    if any(str(code) in exc_str for code in _RETRYABLE_STATUS_CODES):
        return True
    if "timeout" in exc_str or "connection" in exc_str:
        return True
    return False


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """Structured response from an LLM call, including metadata."""
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMProvider(ABC):
    """Abstract LLM provider with built-in retry and token tracking."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return a human-readable provider identifier."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier being used."""

    @abstractmethod
    def _raw_chat(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> LLMResponse:
        """Execute a single LLM call. Subclasses implement this."""

    def chat(
        self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000,
    ) -> str:
        """Chat with retry and tracking. Returns response content string.

        Note: The `temperature` parameter is accepted for interface consistency
        but may be ignored by providers that don't support it.
        """
        if temperature != 0.1 and self.provider_name == "azure":
            logger.debug(
                "Selected Azure deployment does not use the temperature parameter (requested %.2f). "
                "Response variability is model-controlled.",
                temperature,
            )
        return self._call_with_retry(messages, max_tokens, json_mode=False)

    def chat_json(
        self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000,
    ) -> str:
        """Chat with JSON response format, retry, and tracking."""
        return self._call_with_retry(messages, max_tokens, json_mode=True)

    def _call_with_retry(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> str:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            start = time.monotonic()
            try:
                resp = self._raw_chat(messages, max_tokens, json_mode)
                elapsed_ms = (time.monotonic() - start) * 1000
                _token_tracker.record(LLMCallRecord(
                    timestamp=datetime.now(),
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_tokens=resp.prompt_tokens,
                    completion_tokens=resp.completion_tokens,
                    total_tokens=resp.total_tokens,
                    latency_ms=elapsed_ms,
                    success=True,
                ))
                return resp.content
            except Exception as exc:
                elapsed_ms = (time.monotonic() - start) * 1000
                last_exc = exc
                _token_tracker.record(LLMCallRecord(
                    timestamp=datetime.now(),
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=elapsed_ms,
                    success=False,
                    error=str(exc)[:200],
                ))
                if attempt < _MAX_RETRIES - 1 and _is_retryable(exc):
                    delay = _BASE_DELAY_S * (2 ** attempt)
                    logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    break
        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------

class AzureOpenAIProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = AzureOpenAI(
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
        )
        self.deployment = settings.azure_openai_deployment

    @property
    def provider_name(self) -> str:
        return "azure"

    @property
    def model_name(self) -> str:
        return self.deployment

    def _raw_chat(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.deployment,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        # Temperature intentionally omitted for Azure compatibility.
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model or self.deployment,
            provider="azure",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )


# ---------------------------------------------------------------------------
# OpenAI (direct)
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        client_kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**client_kwargs)
        self.model = settings.openai_model

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.model

    def _raw_chat(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model or self.model,
            provider="openai",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    def _raw_chat(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> LLMResponse:
        actual_messages = list(messages)
        if json_mode:
            actual_messages.append({
                "role": "system",
                "content": "Return only valid JSON. Do not include markdown or explanation.",
            })
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": actual_messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": max_tokens},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        # Ollama doesn't always report token counts
        eval_count = data.get("eval_count", 0)
        prompt_eval = data.get("prompt_eval_count", 0)
        return LLMResponse(
            content=content,
            model=self.model,
            provider="ollama",
            prompt_tokens=prompt_eval,
            completion_tokens=eval_count,
            total_tokens=prompt_eval + eval_count,
        )


# ---------------------------------------------------------------------------
# Fallback (no LLM)
# ---------------------------------------------------------------------------

class FallbackProvider(LLMProvider):
    """Rule-based fallback when no LLM API is available."""

    @property
    def provider_name(self) -> str:
        return "fallback"

    @property
    def model_name(self) -> str:
        return "none"

    def _raw_chat(
        self, messages: list[dict], max_tokens: int, json_mode: bool,
    ) -> LLMResponse:
        raise RuntimeError("No LLM provider configured.")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is not None:
        return _provider

    settings = get_settings()
    active = settings.active_provider

    if active == "azure":
        _provider = AzureOpenAIProvider()
    elif active == "openai":
        _provider = OpenAIProvider()
    elif active == "ollama":
        _provider = OllamaProvider()
    else:
        _provider = FallbackProvider()

    logger.info("LLM provider initialized: %s (model=%s)", _provider.provider_name, _provider.model_name)
    return _provider


def reset_provider():
    """Reset the cached provider (useful for testing or config changes)."""
    global _provider
    _provider = None
