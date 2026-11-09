import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import ItemType, Severity, SourceType, VerificationStatus
from app.schemas.common import ORMModel


class SortOrder(StrEnum):
    LATEST = "latest"
    IMPORTANCE = "importance"
    RELEVANCE = "relevance"


class SourceBrief(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    source_type: SourceType
    is_official: bool
    reliability: float


class CategoryOut(ORMModel):
    id: int
    slug: str
    name: str


class AISummary(BaseModel):
    """AI-generated text. Always rendered with an "AI-generated" label, never as source content."""

    short: str
    provider: str
    model: str
    generated_at: datetime


class ArticleOut(ORMModel):
    id: uuid.UUID
    item_type: ItemType
    title: str
    description: str | None
    url: str
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    verification_status: VerificationStatus
    severity: Severity | None
    severity_basis: str | None
    importance_score: float | None = Field(
        None, description="AI Pulse importance score (0-100). Not an official CVSS score."
    )
    tags: list[str]
    source: SourceBrief
    categories: list[CategoryOut]
    duplicate_of_id: uuid.UUID | None
    is_bookmarked: bool = False
    is_read: bool = False
    ai_summary: AISummary | None = None


class ArticleDetail(ArticleOut):
    content: str | None
    content_hash: str
    source_updated_at: datetime | None
    language: str | None


class ArticleFilters(BaseModel):
    q: str | None = Field(None, max_length=300, description="Full-text search over title/description/content")
    item_type: list[ItemType] | None = None
    category: list[str] | None = Field(None, description="Category slugs")
    source: list[str] | None = Field(None, description="Source slugs")
    severity: list[Severity] | None = None
    min_importance: float | None = Field(None, ge=0, le=100)
    verification: list[VerificationStatus] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    include_duplicates: bool = False
    sort: SortOrder = SortOrder.LATEST

    @field_validator("q")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None

    @model_validator(mode="after")
    def _check(self) -> "ArticleFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        if self.sort == SortOrder.RELEVANCE and not self.q:
            self.sort = SortOrder.LATEST
        return self
