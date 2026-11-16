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
    explained_at: datetime | None = Field(None, description="When an AI explanation was generated, if any")


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
    llm_available: bool = False
    kinds: list[FacetCount]
    stack: list[FacetCount]
    sources: list[SourceStatus]
    new_last_7_days: int


class ExplanationPart(BaseModel):
    text: str = Field(description='AI-written, grounded and cited, or "insufficient information"')
    insufficient: bool
    citations: list[int]


class ExplanationSections(BaseModel):
    what_it_does: ExplanationPart
    how_it_helps: ExplanationPart = Field(description="How it could help develop or run AI Pulse")
    how_to_try: ExplanationPart
    cautions: ExplanationPart


class ExplanationSource(BaseModel):
    n: int
    kind: str = Field(description="listing | readme | ai_pulse")
    title: str
    url: str | None


class SkillExplanationOut(BaseModel):
    status: str = Field(description="none (not generated yet) | ready | insufficient | failed (model error)")
    error: str | None = Field(None, description="Why the AI model did not answer (status failed)")
    sections: ExplanationSections | None = None
    sources: list[ExplanationSource] = []
    unsupported_claims_removed: list[str] = []
    ai_generated: bool = False
    provider: str | None = None
    model: str | None = None
    generated_at: datetime | None = None
    listing_version: str | None = Field(
        None, description="The listing version the explanation was written for"
    )
    llm_available: bool
