"""LLM provider abstraction layer. Supports Azure OpenAI, OpenAI, and Ollama."""

from abc import ABC, abstractmethod
import httpx
from openai import AzureOpenAI, OpenAI
from config.settings import get_settings


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        pass

    @abstractmethod
    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        """Chat with JSON response format."""
        pass


class AzureOpenAIProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = AzureOpenAI(
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
        )
        self.deployment = settings.azure_openai_deployment

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class OpenAIProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        json_messages = list(messages) + [
            {
                "role": "system",
                "content": "Return only valid JSON. Do not include markdown or explanation.",
            }
        ]
        return self.chat(json_messages, temperature=temperature, max_tokens=max_tokens)


class FallbackProvider(LLMProvider):
    """Rule-based fallback when no LLM API is available."""

    def chat(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        raise RuntimeError("No LLM provider configured.")

    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 2000) -> str:
        raise RuntimeError("No LLM provider configured.")


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

    return _provider


def reset_provider():
    """Reset the cached provider (useful for testing or config changes)."""
    global _provider
    _provider = None
