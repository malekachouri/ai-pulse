import uuid
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator, model_validator

from app.alerts.engine import AlertSettings
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
    by_kind: dict[str, int] = Field(default_factory=dict)


class NotificationFilters(BaseModel):
    model_config = {"extra": "forbid"}

    unread_only: bool = False
    kind: list[NotificationKind] = Field(default_factory=list)
    severity: list[Severity] = Field(default_factory=list)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


FollowType = Literal["technology", "repository", "provider"]
FOLLOW_FIELD: dict[str, str] = {
    "technology": "followed_technologies",
    "repository": "followed_repositories",
    "provider": "followed_providers",
}
FOLLOW_LIMIT = {"technology": 100, "repository": 100, "provider": 50}


class FollowRequest(BaseModel):
    type: FollowType
    value: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check(self) -> FollowRequest:
        self.value = self.value.strip()
        if not self.value:
            raise ValueError("value must not be blank")
        if self.type == "repository":
            parts = self.value.split("/")
            if len(parts) != 2 or not all(parts):
                raise ValueError(f"Repository '{self.value}' must be in owner/name form")
        elif len(self.value) > 100:
            raise ValueError("Entries must be at most 100 characters")
        return self


class PreferencesOut(ORMModel):
    interests: list[str]
    followed_technologies: list[str]
    followed_repositories: list[str]
    followed_providers: list[str]
    min_notification_severity: Severity
    briefing_frequency: BriefingFrequency
    briefing_hour: int
    briefing_weekday: int = 0
    timezone: str
    theme: str
    alert_settings: AlertSettings = Field(default_factory=AlertSettings)

    @field_validator("alert_settings", mode="before")
    @classmethod
    def _merge_defaults(cls, v: object) -> object:
        return {**AlertSettings().model_dump(), **(v or {})} if isinstance(v, dict) or v is None else v


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
    briefing_weekday: int | None = Field(None, ge=0, le=6, description="Weekly briefings: 0 = Monday")
    timezone: str | None = None
    theme: str | None = Field(None, pattern="^(dark|light|system)$")
    alert_settings: AlertSettings | None = None

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
