"""The shared normalized format every connector produces.

`NormalizedItem` carries the canonical article fields (original content + provenance). Optional typed
payloads carry structured facts for the specialised tables. Unknown values stay `None` - connectors must
never invent data; writers never overwrite a known value with `None`.
"""

import hashlib
import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    BugKind,
    BugResolution,
    IncidentStatus,
    IssueState,
    ItemType,
    Severity,
    VerificationStatus,
)


class VulnerabilityPayload(BaseModel):
    cve_id: str
    description: str | None = None
    cvss_score: float | None = None
    cvss_version: str | None = None
    cvss_vector: str | None = None
    severity: Severity | None = None
    cwe_ids: list[str] | None = None
    affected_products: list[dict[str, Any]] | None = None
    known_exploited: bool | None = None
    kev_date_added: date | None = None
    kev_due_date: date | None = None
    remediation: str | None = None
    patch_available: bool | None = None
    references: list[dict[str, Any]] | None = None
    published_at: datetime | None = None
    last_modified_at: datetime | None = None


class IncidentPayload(BaseModel):
    provider: str
    external_id: str
    title: str
    status: IncidentStatus
    status_page_url: str
    affected_services: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    impact: str | None = None
    started_at: datetime | None = None
    resolved_at: datetime | None = None
    updates: list[dict[str, Any]] = Field(default_factory=list)


class PaperPayload(BaseModel):
    arxiv_id: str | None = None
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    primary_category: str | None = None
    pdf_url: str | None = None
    published_at: datetime | None = None


class ReleasePayload(BaseModel):
    provider: str
    model_name: str
    family: str | None = None
    version: str | None = None
    released_at: datetime | None = None
    modality: list[str] | None = None
    is_open_weights: bool | None = None
    homepage_url: str | None = None
    source_url: str


class RepositoryPayload(BaseModel):
    full_name: str
    html_url: str
    github_id: int | None = None
    description: str | None = None
    language: str | None = None
    topics: list[str] | None = None
    stars: int | None = None
    forks: int | None = None
    open_issues: int | None = None
    pushed_at: datetime | None = None
    latest_release: str | None = None
    latest_release_at: datetime | None = None


class ToolPayload(BaseModel):
    name: str
    repository: str | None = None  # owner/name
    description: str | None = None
    category: str | None = None
    homepage_url: str | None = None
    latest_version: str | None = None
    license: str | None = None


class IssuePayload(BaseModel):
    repository: str  # owner/name
    number: int
    title: str
    html_url: str
    state: IssueState
    labels: list[str] = Field(default_factory=list)
    is_pull_request: bool = False
    comments: int = 0
    opened_at: datetime
    source_updated_at: datetime | None = None
    closed_at: datetime | None = None


class BugPayload(BaseModel):
    project: str
    kind: BugKind
    severity: Severity
    severity_basis: str | None = None
    status: IssueState
    affected_versions: list[str] = Field(default_factory=list)
    fixed_in_version: str | None = None
    fix_url: str | None = None
    fix_merged_at: datetime | None = None
    resolution: BugResolution | None = None
    source_url: str


class NormalizedItem(BaseModel):
    external_id: str = Field(min_length=1, max_length=512)
    item_type: ItemType
    title: str
    url: str
    description: str | None = None
    content: str | None = None
    author: str | None = None
    language: str | None = None
    published_at: datetime | None = None
    source_updated_at: datetime | None = None
    severity: Severity | None = None
    severity_basis: str | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    canonical_key: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    # When False only the typed payload is stored (e.g. old KEV entries: flag CVEs without flooding feeds).
    create_article: bool = True

    vulnerability: VulnerabilityPayload | None = None
    incident: IncidentPayload | None = None
    paper: PaperPayload | None = None
    release: ReleasePayload | None = None
    repository: RepositoryPayload | None = None
    tool: ToolPayload | None = None
    issue: IssuePayload | None = None
    bug: BugPayload | None = None

    def content_hash(self) -> str:
        """Stable hash of everything that represents a *change* in the source record."""
        material = self.model_dump(
            mode="json", exclude={"raw", "create_article", "categories", "tags", "verification"}
        )
        if material.get("repository"):  # star counts change constantly; not a content change
            for k in ("stars", "forks", "open_issues", "pushed_at"):
                material["repository"].pop(k, None)
        blob = json.dumps(material, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()
