"""Application settings, loaded exclusively from environment variables / .env.

No credentials are hardcoded: secrets have no usable defaults and the app refuses
to start in production with the development JWT secret.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-change-me"  # noqa: S105 - sentinel, rejected in production


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Pulse"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aipulse"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    redis_url: str = "redis://localhost:6379/0"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Auth
    jwt_secret: SecretStr = SecretStr(_DEV_SECRET)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-pulse"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    password_reset_ttl_minutes: int = 30
    refresh_cookie_name: str = "aipulse_refresh"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    # Only for local development without an email server: return reset tokens in the API response.
    expose_reset_token: bool = False

    # AI engine. No model names are hardcoded: set LLM_MODEL / EMBEDDING_MODEL for your provider.
    llm_provider: Literal["openai", "ollama", "anthropic", "none"] = "none"
    llm_model: str | None = None
    # Anthropic has no embeddings API: use openai or ollama ("auto" = same as the LLM when it can embed).
    embedding_provider: Literal["auto", "openai", "ollama", "none"] = "auto"
    embedding_model: str | None = None
    embedding_dim: int = 768  # fixed by the pgvector column; OpenAI text-embedding-3-* is asked for 768 dims
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"  # any OpenAI-compatible endpoint
    anthropic_api_key: SecretStr | None = None
    anthropic_api_url: str = "https://api.anthropic.com"
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 90.0
    llm_max_output_tokens: int = 1800
    llm_temperature: float = 0.2
    # Optional pricing (USD per million tokens) for cost tracking - prices change, so they are configuration.
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    ai_batch_size: int = 20  # articles analysed per scheduled run
    ai_daily_token_budget: int | None = None  # stop LLM analysis for the day once reached (None = unlimited)

    # Ingestion
    ingestion_max_attempts: int = 3  # job-level attempts (each HTTP request also retries with backoff)
    ingestion_dispatch_seconds: int = 60  # how often the scheduler looks for due sources
    # Scheduling of personal briefings and alert evaluation (Celery Beat)
    briefing_dispatch_seconds: int = Field(300, ge=60, le=3600)  # how often due briefings are looked up
    briefing_max_retries: int = Field(3, ge=0, le=10)  # per-user generation retries (exponential backoff)
    alerts_interval_seconds: int = Field(300, ge=60, le=3600)
    # Ingestion credentials (optional; connectors degrade gracefully without them)
    github_token: SecretStr | None = None
    nvd_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.environment == "production":
            secret = self.jwt_secret.get_secret_value()
            if secret == _DEV_SECRET or len(secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong value (>=32 chars) in production")
            if self.expose_reset_token:
                raise ValueError("EXPOSE_RESET_TOKEN must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
