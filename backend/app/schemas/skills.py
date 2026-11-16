"""Skills radar API: MCP servers, Claude Code plugins and Agent Skills from official listings."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import SkillKind
from app.schemas.common import ORMModel
from app.schemas.intel import ListParams, _strip
from app.skills.stack import STACK


class SkillFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches name, title, description or publisher")
    kind: list[SkillKind] | None = None
    source: list[str] | None = Field(None, description="Source slugs, e.g. mcp-registry")
    stack: list[str] | None = Field(None, description=f"Any of: {', '.join(STACK)}")
    fits: bool = Field(False, description="Only entries that mention a technology AI Pulse uses")
    days: int | None = Field(
        None, ge=1, le=365, description="New in the last N days (first seen by AI Pulse; baseline excluded)"
    )
    include_inactive: bool = Field(False, description="Also deprecated, deleted or removed entries")

    _q = field_validator("q")(_strip)

    @field_validator("stack")
    @classmethod
    def _known_tags(cls, v: list[str] | None) -> list[str] | None:
        unknown = sorted(set(v or []) - set(STACK))
        if unknown:
            raise ValueError(f"unknown stack tag(s): {', '.join(unknown)}")
        return v


class SkillSource(ORMModel):
    slug: str
    name: str


class InstallStep(BaseModel):
    label: str
    command: str | None
    notes: list[str] = []


class SkillOut(ORMModel):
    id: uuid.UUID
    kind: SkillKind
    name: str
    title: str | None
    description: str | None
    version: str | None
    publisher: str | None
    category: str | None
    status: str
    source: SkillSource
    listing_url: str
    homepage_url: str | None
    repository_url: str | None
    install: list[InstallStep]
    stack_tags: list[str]
    published_at: datetime | None
    source_updated_at: datetime | None
    first_seen_at: datetime
    initial: bool = Field(description="Already listed when AI Pulse started watching the source (not new)")
    is_new: bool = Field(False, description="First seen in the last 7 days and not part of the baseline")


class SkillDetail(SkillOut):
    facts: dict[str, Any]


class FacetCount(BaseModel):
    value: str
    count: int


class SourceStatus(BaseModel):
    slug: str
    name: str
    entries: int
    last_success_at: datetime | None
    last_error: str | None


class SkillFacets(BaseModel):
    kinds: list[FacetCount]
    stack: list[FacetCount]
    sources: list[SourceStatus]
    new_last_7_days: int
