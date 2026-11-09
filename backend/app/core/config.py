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

    # AI (used from phase 5 onwards)
    llm_provider: Literal["openai", "ollama", "anthropic", "none"] = "none"
    llm_model: str | None = None
    embedding_model: str | None = None
    embedding_dim: int = 768
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

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
