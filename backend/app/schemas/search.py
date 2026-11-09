from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ItemType, Severity
from app.schemas.article import ArticleOut
from app.schemas.intel import DateRangeMixin, ListParams

HIGHLIGHT_START = "[["
HIGHLIGHT_END = "]]"


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchParams(ListParams, DateRangeMixin):
    q: str = Field(min_length=2, max_length=300)
    mode: SearchMode = SearchMode.KEYWORD
    item_type: list[ItemType] | None = None
    category: list[str] | None = None
    severity: list[Severity] | None = None

    @field_validator("q")
    @classmethod
    def _q(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Query must be at least 2 characters")
        return v


class SearchHit(BaseModel):
    article: ArticleOut
    rank: float = Field(description="Full-text relevance (ts_rank_cd); comparable only within one query")
    scores: dict[str, float] = Field(
        default_factory=dict, description="Per-signal scores (bm25, semantic, rrf)"
    )
    snippet: str | None = Field(
        None,
        description=f"Plain-text excerpt; matched terms wrapped in {HIGHLIGHT_START} and {HIGHLIGHT_END}",
    )


class SearchCapabilities(BaseModel):
    keyword: bool = True
    semantic: bool
    hybrid: bool
    ask: bool
    ask_mode: str = Field(description="'generative' with an LLM, otherwise 'sources-only'")
    embedded_items: int
    total_items: int


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    item_type: list[ItemType] | None = None
    category: list[str] | None = None
    date_from: datetime | None = None
    max_sources: int = Field(8, ge=1, le=12)


class Citation(BaseModel):
    n: int
    article_id: str
    title: str
    url: str
    source: str
    item_type: str
    published_at: str | None
    importance: float | None
    relevance: dict[str, float]
    ai_summary: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str | None = Field(description="AI-generated; every sentence cites sources as [n]")
    insufficient: bool
    reason: str | None
    citations: list[Citation]
    sources: list[Citation]
    unsupported_claims_removed: list[str]
    retrieval: dict[str, Any]
    generated_by: dict[str, str] | None
    confidence: str | None = None
    ai_generated: bool = True


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    items: list[SearchHit]
    total: int
    page: int
    page_size: int
    pages: int
