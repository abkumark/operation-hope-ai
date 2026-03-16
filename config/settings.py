import logging
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # LLM Provider
    llm_provider: str = Field(default="openai", description="openai | ollama | azure")

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model name")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1")

    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="")
    azure_openai_key: str = Field(default="")
    azure_openai_deployment: str = Field(default="")
    azure_openai_api_version: str = Field(default="2024-12-01-preview")
    azure_openai_embedding_deployment: str = Field(default="text-embedding-ada-002")

    # Vector Store
    chroma_persist_dir: str = Field(default="./data/chroma_db")
    database_path: Path = Field(default=Path("data/app/hope_ai.db"))

    # Confidence Thresholds
    auto_resolve_threshold: float = Field(default=0.85)
    review_threshold: float = Field(default=0.60)

    # Instant resolution: auto-send without human approval when confidence exceeds
    # this threshold AND the category is auto-resolvable.  Set to 0 to disable.
    instant_resolve_threshold: float = Field(
        default=0.95,
        description="Confidence above which AI responses are sent without approval (0 = disabled)",
    )
    instant_resolve_enabled: bool = Field(
        default=False,
        description="Master switch for instant (no-approval) auto-resolution",
    )

    # Dynamics 365
    dynamics_tenant_id: str = Field(default="")
    dynamics_client_id: str = Field(default="")
    dynamics_client_secret: str = Field(default="")
    dynamics_instance_url: str = Field(default="https://oh.crm.dynamics.com")
    dynamics_case_entity: str = Field(default="incidents")
    dynamics_case_id_field: str = Field(default="incidentid")
    dynamics_ticket_number_field: str = Field(default="ticketnumber")
    dynamics_title_field: str = Field(default="title")
    dynamics_description_field: str = Field(default="description")
    dynamics_status_field: str = Field(default="statecode")
    dynamics_customer_name_field: str = Field(default="")
    dynamics_customer_email_field: str = Field(default="")
    dynamics_origin_field: str = Field(default="")
    dynamics_queue_field: str = Field(default="")
    dynamics_ai_category_field: str = Field(default="")
    dynamics_ai_confidence_field: str = Field(default="")
    dynamics_ai_response_field: str = Field(default="")
    dynamics_ai_action_field: str = Field(default="")

    # SMTP Email
    smtp_host: str = Field(default="localhost", description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: str = Field(default="", description="SMTP auth username")
    smtp_password: str = Field(default="", description="SMTP auth password")
    smtp_sender: str = Field(default="noreply@operationhope.org", description="From address")
    smtp_use_tls: bool = Field(default=True, description="Use STARTTLS for SMTP")

    # Application
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    jwt_secret_key: str = Field(
        default="", description="Override JWT secret for production"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )
    auto_ingest_kb_on_startup: bool = Field(default=True)
    use_mock_dynamics: bool = Field(default=True)
    escalation_hours: float = Field(
        default=24.0, description="Hours before an unresolved ticket is escalated"
    )

    # Paths
    knowledge_base_dir: Path = Field(default=Path("data/knowledge_base"))
    sample_tickets_dir: Path = Field(default=Path("data/sample_tickets"))

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _resolve_relative_paths(self) -> "Settings":
        """Resolve relative data paths against the project root so the app
        works regardless of which directory uvicorn is launched from."""
        root = _PROJECT_ROOT

        if not Path(self.chroma_persist_dir).is_absolute():
            self.chroma_persist_dir = str(root / self.chroma_persist_dir)
        if not self.database_path.is_absolute():
            self.database_path = root / self.database_path
        if not self.knowledge_base_dir.is_absolute():
            self.knowledge_base_dir = root / self.knowledge_base_dir
        if not self.sample_tickets_dir.is_absolute():
            self.sample_tickets_dir = root / self.sample_tickets_dir

        return self

    @property
    def is_openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def is_azure_configured(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_key)

    @property
    def active_provider(self) -> str:
        if self.llm_provider == "ollama":
            return "ollama"
        if self.llm_provider == "openai" and self.is_openai_configured:
            return "openai"
        if self.llm_provider == "azure" and self.is_azure_configured:
            return "azure"
        return "fallback"


_settings = None
_validated = False


def _validate_config(settings: Settings) -> None:
    """Log warnings for missing/misconfigured settings at startup."""
    global _validated
    if _validated:
        return
    _validated = True

    warnings = []

    # LLM configuration
    if settings.active_provider == "fallback":
        warnings.append(
            "LLM provider is 'fallback' (rule-based). Set OPENAI_API_KEY, AZURE_OPENAI_KEY, "
            "or LLM_PROVIDER=ollama for AI-powered classification and response generation."
        )

    # SMTP configuration
    if not settings.smtp_username:
        warnings.append(
            "SMTP not configured (SMTP_USERNAME is empty). Emails will be logged but NOT sent. "
            "Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_SENDER in .env for email delivery."
        )

    # JWT secret
    if not settings.jwt_secret_key and settings.app_env != "development":
        warnings.append(
            "JWT_SECRET_KEY is not set. Using a default key is INSECURE for production. "
            "Set JWT_SECRET_KEY in your .env file."
        )

    # Dynamics 365
    if not settings.use_mock_dynamics and not (
        settings.dynamics_tenant_id and settings.dynamics_client_id
    ):
        warnings.append("Dynamics 365 is set to live mode but credentials are missing.")

    for w in warnings:
        logger.warning("⚠️  CONFIG: %s", w)

    if not warnings:
        logger.info("✅ Configuration validated: provider=%s, smtp=%s",
                     settings.active_provider,
                     "configured" if settings.smtp_username else "disabled")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _validate_config(_settings)
    return _settings


def reset_settings():
    global _settings, _validated
    _settings = None
    _validated = False
