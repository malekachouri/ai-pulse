"""Structured, type-specific intelligence entities linked to canonical articles."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BugKind, IncidentStatus, IssueState, Severity, enum_column


def _article_fk(unique: bool = True) -> Mapped[uuid.UUID | None]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL"), unique=unique, nullable=True
    )


class AIModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider", "name", name="uq_ai_models_provider_name"),)

    provider: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    family: Mapped[str | None] = mapped_column(String(100))
    modality: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list, server_default="{}")
    is_open_weights: Mapped[bool | None] = mapped_column(Boolean)
    homepage_url: Mapped[str | None] = mapped_column(String(2048))

    releases: Mapped[list["AIModelRelease"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class AIModelRelease(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_model_releases"
    __table_args__ = (Index("ix_ai_model_releases_released_at", "released_at"),)

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[uuid.UUID | None] = _article_fk(unique=False)
    version: Mapped[str | None] = mapped_column(String(100))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_window: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048))

    model: Mapped[AIModel] = relationship(back_populates="releases")


class AITool(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_tools"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))  # framework, library, platform...
    homepage_url: Mapped[str | None] = mapped_column(String(2048))
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("github_repositories.id", ondelete="SET NULL")
    )
    latest_version: Mapped[str | None] = mapped_column(String(100))
    license: Mapped[str | None] = mapped_column(String(100))
    article_id: Mapped[uuid.UUID | None] = _article_fk(unique=False)

    repository: Mapped["GitHubRepository | None"] = relationship(lazy="joined")


class ResearchPaper(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_papers"
    __table_args__ = (Index("ix_research_papers_published_at", "published_at"),)

    article_id: Mapped[uuid.UUID | None] = _article_fk()
    arxiv_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    doi: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(1000))
    authors: Mapped[list[str]] = mapped_column(ARRAY(String(300)), default=list, server_default="{}")
    abstract: Mapped[str | None] = mapped_column(Text)
    primary_category: Mapped[str | None] = mapped_column(String(32))
    pdf_url: Mapped[str | None] = mapped_column(String(2048))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubRepository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "github_repositories"
    __table_args__ = (Index("ix_github_repositories_stars", "stars"),)

    full_name: Mapped[str] = mapped_column(String(200), unique=True)  # owner/name
    github_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    html_url: Mapped[str] = mapped_column(String(2048))
    language: Mapped[str | None] = mapped_column(String(64))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    stars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    forks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    open_issues: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stars_delta_7d: Mapped[int | None] = mapped_column(Integer)  # computed from our own snapshots
    latest_release: Mapped[str | None] = mapped_column(String(100))
    latest_release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    star_history: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    tracked: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class GitHubIssue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "github_issues"
    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_github_issues_repo_number"),
        Index("ix_github_issues_state_opened", "state", "opened_at"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("github_repositories.id", ondelete="CASCADE"), index=True
    )
    article_id: Mapped[uuid.UUID | None] = _article_fk()
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(1000))
    html_url: Mapped[str] = mapped_column(String(2048))
    state: Mapped[IssueState] = mapped_column(enum_column(IssueState, "issue_state"))
    labels: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list, server_default="{}")
    is_pull_request: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    comments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped[GitHubRepository] = relationship(lazy="joined")


class SoftwareBug(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "software_bugs"
    __table_args__ = (Index("ix_software_bugs_severity_created", "severity", "created_at"),)

    article_id: Mapped[uuid.UUID | None] = _article_fk()
    github_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("github_issues.id", ondelete="SET NULL"), unique=True
    )
    project: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[BugKind] = mapped_column(enum_column(BugKind, "bug_kind"))
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    severity_basis: Mapped[str | None] = mapped_column(String(200))  # e.g. "label: priority/critical"
    status: Mapped[IssueState] = mapped_column(enum_column(IssueState, "issue_state"))
    affected_versions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    fixed_in_version: Mapped[str | None] = mapped_column(String(64))
    fix_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str] = mapped_column(String(2048))

    github_issue: Mapped["GitHubIssue | None"] = relationship(lazy="joined")
    article: Mapped["Article | None"] = relationship(lazy="joined")  # noqa: F821 - resolved by registry


class SecurityVulnerability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "security_vulnerabilities"
    __table_args__ = (
        CheckConstraint("cvss_score IS NULL OR (cvss_score BETWEEN 0 AND 10)", name="cvss_range"),
        Index("ix_security_vulnerabilities_published", "published_at"),
        Index("ix_security_vulnerabilities_severity", "severity"),
        Index("ix_security_vulnerabilities_cvss", "cvss_score"),
        Index("ix_security_vulnerabilities_modified", "last_modified_at"),
    )

    article_id: Mapped[uuid.UUID | None] = _article_fk()
    cve_id: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    cvss_score: Mapped[float | None] = mapped_column(Float)  # official score only, never estimated
    cvss_version: Mapped[str | None] = mapped_column(String(8))
    cvss_vector: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    cwe_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list, server_default="{}")
    affected_products: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    known_exploited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    kev_date_added: Mapped[date | None] = mapped_column(Date)
    kev_due_date: Mapped[date | None] = mapped_column(Date)
    remediation: Mapped[str | None] = mapped_column(Text)  # only from official sources
    patch_available: Mapped[bool | None] = mapped_column(Boolean)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Incident(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_incidents_provider_external"),
        Index("ix_incidents_status_verified", "status", "last_verified_at"),
        Index("ix_incidents_started_at", "started_at"),
    )

    article_id: Mapped[uuid.UUID | None] = _article_fk()
    provider: Mapped[str] = mapped_column(String(100), index=True)  # aws, azure, gcp, openai...
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(1000))
    affected_services: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), default=list, server_default="{}"
    )
    regions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    status: Mapped[IncidentStatus] = mapped_column(enum_column(IncidentStatus, "incident_status"))
    impact: Mapped[str | None] = mapped_column(String(64))  # as reported by the provider
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_page_url: Mapped[str] = mapped_column(String(2048))
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # last status-page check
    updates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")
