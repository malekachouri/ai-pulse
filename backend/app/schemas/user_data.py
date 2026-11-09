import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BriefingFrequency, NotificationKind, Severity
from app.schemas.article import ArticleOut
from app.schemas.common import ORMModel

INTERESTS = [
    "ai-engineering", "generative-ai", "rag", "ai-agents", "llmops", "devops", "cloud",
    "kubernetes", "cybersecurity", "software-engineering",
]  # fmt: skip


class BookmarkOut(BaseModel):
    id: uuid.UUID
    note: str | None
    created_at: datetime
    article: ArticleOut


class BookmarkUpsert(BaseModel):
    note: str | None = Field(None, max_length=2000)


class NotificationOut(ORMModel):
    id: uuid.UUID
    kind: NotificationKind
    severity: Severity
    title: str
    body: str | None
    article_id: uuid.UUID | None
    link: str | None
    created_at: datetime
    read_at: datetime | None


class UnreadCount(BaseModel):
    unread: int


class PreferencesOut(ORMModel):
    interests: list[str]
    followed_technologies: list[str]
    followed_repositories: list[str]
    followed_providers: list[str]
    min_notification_severity: Severity
    briefing_frequency: BriefingFrequency
    briefing_hour: int
    timezone: str
    theme: str


def _clean_list(v: list[str], max_len: int) -> list[str]:
    seen: list[str] = []
    for item in v:
        item = item.strip()
        if not item:
            continue
        if len(item) > max_len:
            raise ValueError(f"Entries must be at most {max_len} characters")
        if item.lower() not in (s.lower() for s in seen):
            seen.append(item)
    return seen


class PreferencesUpdate(BaseModel):
    interests: list[str] | None = Field(None, max_length=len(INTERESTS))
    followed_technologies: list[str] | None = Field(None, max_length=100)
    followed_repositories: list[str] | None = Field(None, max_length=100)
    followed_providers: list[str] | None = Field(None, max_length=50)
    min_notification_severity: Severity | None = None
    briefing_frequency: BriefingFrequency | None = None
    briefing_hour: int | None = Field(None, ge=0, le=23)
    timezone: str | None = None
    theme: str | None = Field(None, pattern="^(dark|light|system)$")

    @field_validator("interests")
    @classmethod
    def _interests(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [i for i in v if i not in INTERESTS]
        if bad:
            raise ValueError(f"Unknown interests: {', '.join(bad)}")
        return list(dict.fromkeys(v))

    @field_validator("followed_technologies", "followed_providers")
    @classmethod
    def _short_lists(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _clean_list(v, 100)

    @field_validator("followed_repositories")
    @classmethod
    def _repos(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        cleaned = _clean_list(v, 200)
        for r in cleaned:
            parts = r.split("/")
            if len(parts) != 2 or not all(parts):
                raise ValueError(f"Repository '{r}' must be in owner/name form")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and v not in available_timezones():
            raise ValueError(f"Unknown timezone '{v}'")
        return v


class BriefingOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    briefing_date: date
    period_start: datetime
    period_end: datetime
    executive_summary: str | None
    sections: dict[str, Any]
    cited_article_ids: list[str]
    llm_provider: str | None
    llm_model: str | None
    generated_at: datetime


class BriefingListItem(ORMModel):
    id: uuid.UUID
    briefing_date: date
    executive_summary: str | None
    generated_at: datetime
    personalized: bool = False
