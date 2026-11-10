"""Schemas for the typed intelligence modules (models, tools, research, GitHub, bugs, security, incidents).

Filter models are bound as query parameters (`Annotated[XFilters, Query()]`). Every list endpoint shares
`page`, `page_size` and a whitelisted `sort` (`field` ascending, `-field` descending).
"""

import re
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import BugKind, BugResolution, IncidentStatus, IssueState, Severity
from app.schemas.common import ORMModel, PageParams

CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")


class ListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort: str | None = Field(None, max_length=40, description="Field name; prefix with '-' for descending")

    @property
    def paging(self) -> PageParams:
        return PageParams(page=self.page, page_size=self.page_size)


class DateRangeMixin(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None

    @model_validator(mode="after")
    def _range(self) -> DateRangeMixin:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self


def _strip(v: str | None) -> str | None:
    return (v.strip() or None) if v else None


# ---------------------------------------------------------------- AI models
class ModelFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches model name or family")
    provider: list[str] | None = None
    open_weights: bool | None = None
    modality: str | None = Field(None, max_length=32)

    _q = field_validator("q")(_strip)


class ReleaseBrief(ORMModel):
    id: uuid.UUID
    version: str | None
    released_at: datetime | None
    context_window: int | None
    notes: str | None
    source_url: str
    article_id: uuid.UUID | None


class AIModelOut(ORMModel):
    id: uuid.UUID
    provider: str
    name: str
    family: str | None
    modality: list[str]
    is_open_weights: bool | None
    homepage_url: str | None
    created_at: datetime
    updated_at: datetime
    latest_release: ReleaseBrief | None = None
    release_count: int = 0


class AIModelDetail(AIModelOut):
    releases: list[ReleaseBrief] = []


class ReleaseFilters(ListParams, DateRangeMixin):
    provider: list[str] | None = None
    model_id: uuid.UUID | None = None


class ModelBrief(ORMModel):
    id: uuid.UUID
    provider: str
    name: str


class ReleaseOut(ReleaseBrief):
    model: ModelBrief


# ---------------------------------------------------------------- AI tools
class ToolFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches name or description")
    category: list[str] | None = None
    license: str | None = Field(None, max_length=100)

    _q = field_validator("q")(_strip)


class RepoBrief(ORMModel):
    id: uuid.UUID
    full_name: str
    html_url: str
    stars: int


class AIToolOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    homepage_url: str | None
    latest_version: str | None
    license: str | None
    article_id: uuid.UUID | None
    repository: RepoBrief | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- research
class ResearchFilters(ListParams, DateRangeMixin):
    q: str | None = Field(None, max_length=200, description="Matches title or abstract")
    primary_category: list[str] | None = Field(None, description="e.g. cs.CL, cs.LG")
    author: str | None = Field(None, max_length=200)

    _q = field_validator("q", "author")(_strip)


class ResearchPaperOut(ORMModel):
    id: uuid.UUID
    arxiv_id: str | None
    doi: str | None
    title: str
    authors: list[str]
    abstract: str | None
    primary_category: str | None
    pdf_url: str | None
    published_at: datetime | None
    article_id: uuid.UUID | None
    created_at: datetime


# ---------------------------------------------------------------- GitHub
class RepoFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches owner/name or description")
    language: list[str] | None = None
    topic: str | None = Field(None, max_length=64)
    min_stars: int | None = Field(None, ge=0)
    tracked: bool | None = None

    _q = field_validator("q")(_strip)


class GitHubRepositoryOut(ORMModel):
    id: uuid.UUID
    full_name: str
    description: str | None
    html_url: str
    language: str | None
    topics: list[str]
    stars: int
    forks: int
    open_issues: int
    stars_delta_7d: int | None = Field(
        None, description="Stars gained over 7 days, computed from AI Pulse's own snapshots"
    )
    latest_release: str | None
    latest_release_at: datetime | None
    pushed_at: datetime | None
    tracked: bool
    updated_at: datetime


class GitHubRepositoryDetail(GitHubRepositoryOut):
    star_history: list[dict[str, Any]]


class IssueFilters(ListParams, DateRangeMixin):
    q: str | None = Field(None, max_length=200)
    repository: list[str] | None = Field(None, description="owner/name")
    state: IssueState | None = None
    label: str | None = Field(None, max_length=100)
    is_pull_request: bool | None = None

    _q = field_validator("q")(_strip)


class GitHubIssueOut(ORMModel):
    id: uuid.UUID
    repository: RepoBrief
    number: int
    title: str
    html_url: str
    state: IssueState
    labels: list[str]
    is_pull_request: bool
    comments: int
    opened_at: datetime
    source_updated_at: datetime | None
    closed_at: datetime | None
    article_id: uuid.UUID | None


# ---------------------------------------------------------------- bugs
class BugFilters(ListParams):
    q: str | None = Field(None, max_length=200, description="Matches project or title")
    project: list[str] | None = None
    kind: list[BugKind] | None = None
    severity: list[Severity] | None = None
    status: IssueState | None = None
    has_fix: bool | None = None
    resolution: list[BugResolution] | None = None
    reported_within_days: int | None = Field(None, ge=1, le=365, description="Newly reported bugs")

    _q = field_validator("q")(_strip)


class SoftwareBugOut(ORMModel):
    id: uuid.UUID
    title: str
    project: str
    kind: BugKind
    severity: Severity
    severity_basis: str | None
    status: IssueState
    affected_versions: list[str]
    fixed_in_version: str | None
    fix_url: str | None = Field(None, description="Merged pull request or closing commit, if linked")
    fix_merged_at: datetime | None = None
    resolution: BugResolution | None = None
    source_url: str
    last_verified_at: datetime | None = None
    issue_number: int | None = None
    repository: str | None = None
    labels: list[str] = []
    opened_at: datetime | None = None
    source_updated_at: datetime | None = None
    article_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- security
class VulnerabilityFilters(ListParams, DateRangeMixin):
    q: str | None = Field(None, max_length=200, description="CVE id or description text")
    severity: list[Severity] | None = None
    min_cvss: float | None = Field(None, ge=0, le=10)
    known_exploited: bool | None = None
    patch_available: bool | None = None
    product: str | None = Field(None, max_length=200, description="Matches affected vendor/product")
    cwe: str | None = Field(None, pattern=r"^CWE-\d+$")

    _q = field_validator("q", "product")(_strip)


class VulnerabilityOut(ORMModel):
    id: uuid.UUID
    cve_id: str
    description: str | None
    cvss_score: float | None = Field(None, description="Official CVSS base score; null if not published")
    cvss_version: str | None
    cvss_vector: str | None
    severity: Severity
    cwe_ids: list[str]
    affected_products: list[dict[str, Any]]
    known_exploited: bool
    kev_date_added: date | None
    kev_due_date: date | None
    patch_available: bool | None
    remediation: str | None = Field(None, description="Mitigation from official sources only (CISA, vendor)")
    references: list[dict[str, Any]] = []
    published_at: datetime | None
    last_modified_at: datetime | None
    last_verified_at: datetime | None = None
    article_id: uuid.UUID | None
    updated_at: datetime


class VulnerabilityDetail(VulnerabilityOut):
    pass


class SecurityStats(BaseModel):
    total: int
    by_severity: dict[str, int]
    known_exploited: int
    published_last_7d: int
    critical_last_7d: int


# ---------------------------------------------------------------- incidents
class IncidentFilters(ListParams, DateRangeMixin):
    q: str | None = Field(None, max_length=200)
    provider: list[str] | None = None
    status: list[IncidentStatus] | None = None
    active_only: bool = Field(
        False,
        description="Unresolved per the provider's status page AND verified within the freshness window",
    )
    state: Literal["current", "historical", "unverified"] | None = Field(
        None, description="current = active and recently verified; historical = resolved; unverified = stale"
    )
    category: (
        list[
            Literal[
                "ai_provider",
                "cloud",
                "api",
                "database",
                "kubernetes_docker",
                "infrastructure",
                "developer_platform",
            ]
        ]
        | None
    ) = None

    _q = field_validator("q")(_strip)


class IncidentOut(ORMModel):
    id: uuid.UUID
    provider: str
    external_id: str
    title: str
    affected_services: list[str]
    regions: list[str]
    status: IncidentStatus
    impact: str | None
    started_at: datetime | None
    resolved_at: datetime | None
    status_page_url: str
    last_verified_at: datetime
    article_id: uuid.UUID | None
    is_active: bool = False
    status_is_stale: bool = Field(
        False, description="Unresolved, but not re-verified recently; do not treat as live"
    )
    state: str = "unverified"
    categories: list[str] = []
    duration_minutes: int | None = None


class IncidentDetail(IncidentOut):
    updates: list[dict[str, Any]]


def validate_cve(cve_id: str) -> str:
    cve = cve_id.strip().upper()
    if not CVE_RE.match(cve):
        raise ValueError("Invalid CVE identifier (expected CVE-YYYY-NNNN)")
    return cve


class CountRow(BaseModel):
    key: str
    count: int


class AffectedTechnology(BaseModel):
    name: str
    vulnerabilities: int
    bugs: int
    incidents: int
    total: int


class IncidentDay(BaseModel):
    day: date
    total: int
    by_provider: dict[str, int]


class WeeklyStats(BaseModel):
    week_start: date
    incidents: int
    outage_minutes: int
    critical_high_cves: int
    kev_added: int
    bugs_reported: int
    bugs_fixed: int


class RadarSummary(BaseModel):
    generated_at: datetime
    window_days: int
    critical_bugs: list[SoftwareBugOut]
    new_vulnerabilities: list[VulnerabilityOut]
    newly_exploited: list[VulnerabilityOut]
    active_incidents: list[IncidentOut]
    resolved_incidents: list[IncidentOut]
    unverified_incidents: int
    severity_chart: list[CountRow]
    most_affected: list[AffectedTechnology]
    incident_history: list[IncidentDay]
    weekly: list[WeeklyStats]
