from enum import StrEnum

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
    snippet: str | None = Field(
        None,
        description=f"Plain-text excerpt; matched terms wrapped in {HIGHLIGHT_START} and {HIGHLIGHT_END}",
    )


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    items: list[SearchHit]
    total: int
    page: int
    page_size: int
    pages: int
