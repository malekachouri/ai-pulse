from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImportanceFactor(BaseModel):
    name: str
    value: float
    weight: float
    contribution: float
    reason: str


class ImportanceBreakdown(BaseModel):
    score: float = Field(description="AI Pulse importance 0-100. Not an official CVSS score.")
    label: str
    version: str
    factors: list[ImportanceFactor]
    excluded: list[str]
    personal_score: float | None = None
    personal_reasons: list[str] = []


class AnalysisStatus(BaseModel):
    status: str = Field(description="ready | pending | failed | disabled")
    provider: str | None = None
    model: str | None = None
    generated_at: datetime | None = None
    error: str | None = None


class ArticleAnalysisOut(BaseModel):
    article_id: str
    ai_generated_notice: str = (
        "Summary, impact and recommendations are AI-generated from the original source."
    )
    summary: dict[str, Any] | None
    summary_status: AnalysisStatus
    importance: ImportanceBreakdown | None
    language: str | None
    keywords: list[str]
    entities: list[dict[str, str]]
    changes: dict[str, Any] | None = Field(
        None,
        description="Release items: what changed since the previous release of the same model, tool or "
        "repository, extracted from both sources (rule-based; 'not documented' when a source does not say).",
    )


class AIStatus(BaseModel):
    llm_provider: str | None
    llm_model: str | None
    embedding_provider: str | None
    embedding_model: str | None
    problems: list[str]
    items_total: int
    items_with_rules_analysis: int
    items_with_ai_summary: int
    items_with_embedding: int
    failed_analyses: int
    tokens_today: int
    cost_today_usd: float | None
    calls_today: int
    errors_today: int
