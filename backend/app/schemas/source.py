import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.models.enums import ItemType, SourceType
from app.schemas.common import ORMModel


class SourceBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    source_type: SourceType
    connector: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_.-]+$")
    url: HttpUrl
    homepage_url: HttpUrl | None = None
    default_item_type: ItemType
    is_official: bool = False
    reliability: float = Field(0.5, ge=0, le=1)
    enabled: bool = True
    poll_interval_minutes: int = Field(60, ge=5, le=10080)
    config: dict[str, Any] = Field(default_factory=dict)


class SourceCreate(SourceBase):
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class SourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    url: HttpUrl | None = None
    homepage_url: HttpUrl | None = None
    is_official: bool | None = None
    reliability: float | None = Field(None, ge=0, le=1)
    enabled: bool | None = None
    poll_interval_minutes: int | None = Field(None, ge=5, le=10080)
    config: dict[str, Any] | None = None


class SourceOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    source_type: SourceType
    connector: str
    url: str
    homepage_url: str | None
    default_item_type: ItemType
    is_official: bool
    reliability: float
    enabled: bool
    poll_interval_minutes: int
    config: dict[str, Any]
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime
