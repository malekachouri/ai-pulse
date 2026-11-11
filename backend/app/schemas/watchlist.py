from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.article import ArticleOut


class WatchRelease(BaseModel):
    article_id: str
    title: str
    url: str = Field(description="Original source of the release")
    version: str | None = None
    published_at: datetime | None = None
    source: str


class WatchEntryOut(BaseModel):
    term: str
    kind: str = Field(description="technology | provider | repository (from the followed_* preferences)")
    total: int = Field(description="Matching items collected in the window")
    new_this_week: int
    latest_release: WatchRelease | None = None
    open_critical_bugs: int | None = Field(
        None, description="Repositories only: open bugs the project labelled critical"
    )
    vulnerabilities: int
    items: list[ArticleOut] = Field(description="Newest first; each links to its original source")


class WatchlistOut(BaseModel):
    entries: list[WatchEntryOut]
    window_days: int
    note: str | None = None
    method: str = (
        "Whole-word mentions in title, description or tags; releases of followed repositories by release "
        "key or URL; model releases of followed providers. Nothing is generated."
    )
