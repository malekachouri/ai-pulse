from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

Status = Literal["ok", "degraded", "down"]


class Check(BaseModel):
    name: str
    status: Status
    detail: str | None = None
    latency_ms: float | None = None
    data: dict[str, Any] = {}


class SystemHealth(BaseModel):
    status: Status
    environment: str
    version: str
    started_at: datetime
    checked_at: datetime
    checks: list[Check]


class DayValue(BaseModel):
    day: date
    value: float


class AIUsageRow(BaseModel):
    provider: str
    model: str
    purpose: str
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class AIUsageDay(BaseModel):
    day: date
    calls: int
    errors: int
    tokens: int
    cost_usd: float | None


class UsageStats(BaseModel):
    window_days: int
    generated_at: datetime
    users_total: int
    users_active: int
    users_by_role: dict[str, int]
    users_new: int
    users_logged_in_7d: int
    signups_by_day: list[DayValue]
    articles_total: int
    articles_by_day: list[DayValue]
    articles_by_type: dict[str, int]
    bookmarks_total: int
    notifications_by_day: list[DayValue]
    notifications_by_kind: dict[str, int]
    notifications_read_ratio: float | None
    briefings_by_day: list[DayValue]
    ai_by_day: list[AIUsageDay]
    ai_by_model: list[AIUsageRow]
    ai_tokens_total: int
    ai_cost_total_usd: float | None
    ai_daily_token_budget: int | None


class AIConfigView(BaseModel):
    """Effective AI configuration. Values come from environment variables only; secrets are never returned."""

    llm_provider: str
    llm_model: str | None
    embedding_provider: str
    embedding_model: str | None
    embedding_dim: int
    openai_base_url: str
    anthropic_api_url: str
    ollama_base_url: str
    openai_api_key_set: bool
    anthropic_api_key_set: bool
    llm_timeout_seconds: float
    llm_max_output_tokens: int
    llm_temperature: float
    llm_price_input_per_mtok: float | None
    llm_price_output_per_mtok: float | None
    ai_batch_size: int
    ai_daily_token_budget: int | None


class BulkRetryResult(BaseModel):
    retried: int
    task_ids: list[str]
    skipped_sources: list[str]
