"""Query construction for the typed intelligence modules. All SQL for these entities lives here."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, String, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AIModel,
    AIModelRelease,
    AITool,
    Article,
    GitHubIssue,
    GitHubRepository,
    Incident,
    ResearchPaper,
    SecurityVulnerability,
    SoftwareBug,
)
from app.models.enums import IncidentStatus, Severity
from app.repositories.base import SortSpec, contains_pattern, paginate
from app.schemas.intel import (
    BugFilters,
    IncidentFilters,
    IssueFilters,
    ModelFilters,
    ReleaseFilters,
    RepoFilters,
    ResearchFilters,
    ToolFilters,
    VulnerabilityFilters,
)

# An incident is "active" only if the provider's own status says unresolved AND we re-checked it recently.
ACTIVE_INCIDENT_WINDOW = timedelta(hours=2)
UNRESOLVED = (IncidentStatus.INVESTIGATING, IncidentStatus.IDENTIFIED, IncidentStatus.MONITORING)


def severity_rank(col: Any) -> ColumnElement[int]:
    """Orderable severity (critical=5 … info=1, unknown=0) — enum strings don't sort meaningfully."""
    return case(
        {Severity.CRITICAL: 5, Severity.HIGH: 4, Severity.MEDIUM: 3, Severity.LOW: 2, Severity.INFO: 1},
        value=col,
        else_=0,
    )


def incident_is_active(now: datetime) -> ColumnElement[bool]:
    return and_(Incident.status.in_(UNRESOLVED), Incident.last_verified_at >= now - ACTIVE_INCIDENT_WINDOW)


def _ilike_any(text: str, *cols: Any) -> ColumnElement[bool]:
    pattern = contains_pattern(text)
    return or_(*(c.ilike(pattern, escape="\\") for c in cols))


def _date_range(stmt: Any, col: Any, f: Any) -> Any:
    if f.date_from:
        stmt = stmt.where(col >= f.date_from)
    if f.date_to:
        stmt = stmt.where(col <= f.date_to)
    return stmt


MODEL_SORT = SortSpec(
    {"name": AIModel.name, "provider": AIModel.provider, "created_at": AIModel.created_at,
     "updated_at": AIModel.updated_at},
    default="-updated_at", tiebreaker=AIModel.id,
)  # fmt: skip
RELEASE_SORT = SortSpec(
    {"released_at": func.coalesce(AIModelRelease.released_at, AIModelRelease.created_at)},
    default="-released_at", tiebreaker=AIModelRelease.id,
)  # fmt: skip
TOOL_SORT = SortSpec(
    {"name": AITool.name, "created_at": AITool.created_at, "updated_at": AITool.updated_at},
    default="name", tiebreaker=AITool.id,
)  # fmt: skip
RESEARCH_SORT = SortSpec(
    {"published_at": ResearchPaper.published_at, "title": ResearchPaper.title,
     "created_at": ResearchPaper.created_at},
    default="-published_at", tiebreaker=ResearchPaper.id,
)  # fmt: skip
REPO_SORT = SortSpec(
    {"stars": GitHubRepository.stars, "stars_delta_7d": GitHubRepository.stars_delta_7d,
     "forks": GitHubRepository.forks, "pushed_at": GitHubRepository.pushed_at,
     "full_name": GitHubRepository.full_name},
    default="-stars", tiebreaker=GitHubRepository.id,
)  # fmt: skip
ISSUE_SORT = SortSpec(
    {"opened_at": GitHubIssue.opened_at, "updated_at": GitHubIssue.source_updated_at,
     "comments": GitHubIssue.comments},
    default="-opened_at", tiebreaker=GitHubIssue.id,
)  # fmt: skip
BUG_SORT = SortSpec(
    {"created_at": SoftwareBug.created_at, "updated_at": SoftwareBug.updated_at,
     "severity": severity_rank(SoftwareBug.severity)},
    default="-created_at", tiebreaker=SoftwareBug.id,
)  # fmt: skip
VULN_SORT = SortSpec(
    {"published_at": SecurityVulnerability.published_at,
     "last_modified_at": SecurityVulnerability.last_modified_at,
     "cvss_score": SecurityVulnerability.cvss_score,
     "severity": severity_rank(SecurityVulnerability.severity),
     "kev_date_added": SecurityVulnerability.kev_date_added},
    default="-published_at", tiebreaker=SecurityVulnerability.id,
)  # fmt: skip
INCIDENT_SORT = SortSpec(
    {"started_at": Incident.started_at, "last_verified_at": Incident.last_verified_at,
     "resolved_at": Incident.resolved_at},
    default="-started_at", tiebreaker=Incident.id,
)  # fmt: skip


class IntelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ------------------------------------------------------------ models
    async def list_models(self, f: ModelFilters) -> tuple[Sequence[AIModel], int]:
        stmt = select(AIModel)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, AIModel.name, AIModel.family))
        if f.provider:
            stmt = stmt.where(func.lower(AIModel.provider).in_([p.lower() for p in f.provider]))
        if f.open_weights is not None:
            stmt = stmt.where(AIModel.is_open_weights.is_(f.open_weights))
        if f.modality:
            stmt = stmt.where(AIModel.modality.any(f.modality))
        return await paginate(self.s, stmt, MODEL_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def release_stats(
        self, model_ids: Sequence[uuid.UUID]
    ) -> tuple[dict[uuid.UUID, AIModelRelease], dict[uuid.UUID, int]]:
        if not model_ids:
            return {}, {}
        when = func.coalesce(AIModelRelease.released_at, AIModelRelease.created_at)
        latest = await self.s.scalars(
            select(AIModelRelease)
            .where(AIModelRelease.model_id.in_(model_ids))
            .order_by(AIModelRelease.model_id, when.desc())
            .distinct(AIModelRelease.model_id)
        )
        counts = await self.s.execute(
            select(AIModelRelease.model_id, func.count())
            .where(AIModelRelease.model_id.in_(model_ids))
            .group_by(AIModelRelease.model_id)
        )
        return {r.model_id: r for r in latest}, dict(counts.tuples().all())

    async def get_model(self, model_id: uuid.UUID) -> AIModel | None:
        return await self.s.scalar(
            select(AIModel).where(AIModel.id == model_id).options(selectinload(AIModel.releases))
        )

    async def list_releases(self, f: ReleaseFilters) -> tuple[Sequence[AIModelRelease], int]:
        when = func.coalesce(AIModelRelease.released_at, AIModelRelease.created_at)
        stmt = select(AIModelRelease).join(AIModel).options(selectinload(AIModelRelease.model))
        if f.provider:
            stmt = stmt.where(func.lower(AIModel.provider).in_([p.lower() for p in f.provider]))
        if f.model_id:
            stmt = stmt.where(AIModelRelease.model_id == f.model_id)
        stmt = _date_range(stmt, when, f)
        return await paginate(self.s, stmt, RELEASE_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    # ------------------------------------------------------------ tools
    async def list_tools(self, f: ToolFilters) -> tuple[Sequence[AITool], int]:
        stmt = select(AITool)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, AITool.name, AITool.description))
        if f.category:
            stmt = stmt.where(AITool.category.in_(f.category))
        if f.license:
            stmt = stmt.where(func.lower(AITool.license) == f.license.lower())
        return await paginate(self.s, stmt, TOOL_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_tool(self, tool_id: uuid.UUID) -> AITool | None:
        return await self.s.get(AITool, tool_id)

    # ------------------------------------------------------------ research
    async def list_papers(self, f: ResearchFilters) -> tuple[Sequence[ResearchPaper], int]:
        stmt = select(ResearchPaper)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, ResearchPaper.title, ResearchPaper.abstract))
        if f.primary_category:
            stmt = stmt.where(ResearchPaper.primary_category.in_(f.primary_category))
        if f.author:
            stmt = stmt.where(_ilike_any(f.author, func.array_to_string(ResearchPaper.authors, " | ")))
        stmt = _date_range(stmt, ResearchPaper.published_at, f)
        return await paginate(self.s, stmt, RESEARCH_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_paper(self, key: str) -> ResearchPaper | None:
        try:
            return await self.s.get(ResearchPaper, uuid.UUID(key))
        except ValueError:
            return await self.s.scalar(select(ResearchPaper).where(ResearchPaper.arxiv_id == key))

    # ------------------------------------------------------------ GitHub
    async def list_repos(self, f: RepoFilters) -> tuple[Sequence[GitHubRepository], int]:
        stmt = select(GitHubRepository)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, GitHubRepository.full_name, GitHubRepository.description))
        if f.language:
            stmt = stmt.where(func.lower(GitHubRepository.language).in_([x.lower() for x in f.language]))
        if f.topic:
            stmt = stmt.where(GitHubRepository.topics.any(f.topic.lower()))
        if f.min_stars is not None:
            stmt = stmt.where(GitHubRepository.stars >= f.min_stars)
        if f.tracked is not None:
            stmt = stmt.where(GitHubRepository.tracked.is_(f.tracked))
        return await paginate(self.s, stmt, REPO_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_repo(self, repo_id: uuid.UUID) -> GitHubRepository | None:
        return await self.s.get(GitHubRepository, repo_id)

    async def get_repo_by_name(self, full_name: str) -> GitHubRepository | None:
        return await self.s.scalar(
            select(GitHubRepository).where(func.lower(GitHubRepository.full_name) == full_name.lower())
        )

    async def list_issues(self, f: IssueFilters) -> tuple[Sequence[GitHubIssue], int]:
        stmt = select(GitHubIssue).join(GitHubRepository)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, GitHubIssue.title))
        if f.repository:
            stmt = stmt.where(func.lower(GitHubRepository.full_name).in_([r.lower() for r in f.repository]))
        if f.state:
            stmt = stmt.where(GitHubIssue.state == f.state)
        if f.label:
            stmt = stmt.where(GitHubIssue.labels.any(f.label))
        if f.is_pull_request is not None:
            stmt = stmt.where(GitHubIssue.is_pull_request.is_(f.is_pull_request))
        stmt = _date_range(stmt, GitHubIssue.opened_at, f)
        return await paginate(self.s, stmt, ISSUE_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    # ------------------------------------------------------------ bugs
    async def list_bugs(self, f: BugFilters) -> tuple[Sequence[SoftwareBug], int]:
        stmt = (
            select(SoftwareBug)
            .outerjoin(GitHubIssue, GitHubIssue.id == SoftwareBug.github_issue_id)
            .outerjoin(Article, Article.id == SoftwareBug.article_id)
        )
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, SoftwareBug.project, GitHubIssue.title, Article.title))
        if f.project:
            stmt = stmt.where(func.lower(SoftwareBug.project).in_([p.lower() for p in f.project]))
        if f.kind:
            stmt = stmt.where(SoftwareBug.kind.in_(f.kind))
        if f.severity:
            stmt = stmt.where(SoftwareBug.severity.in_(f.severity))
        if f.status:
            stmt = stmt.where(SoftwareBug.status == f.status)
        if f.has_fix is not None:
            has = or_(SoftwareBug.fix_url.is_not(None), SoftwareBug.fixed_in_version.is_not(None))
            stmt = stmt.where(has if f.has_fix else ~has)
        return await paginate(self.s, stmt, BUG_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_bug(self, bug_id: uuid.UUID) -> SoftwareBug | None:
        return await self.s.get(SoftwareBug, bug_id)

    # ------------------------------------------------------------ security
    async def list_vulns(self, f: VulnerabilityFilters) -> tuple[Sequence[SecurityVulnerability], int]:
        v = SecurityVulnerability
        stmt = select(v)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, v.cve_id, v.description))
        if f.severity:
            stmt = stmt.where(v.severity.in_(f.severity))
        if f.min_cvss is not None:
            stmt = stmt.where(v.cvss_score >= f.min_cvss)
        if f.known_exploited is not None:
            stmt = stmt.where(v.known_exploited.is_(f.known_exploited))
        if f.patch_available is not None:
            stmt = stmt.where(v.patch_available.is_(f.patch_available))
        if f.product:
            stmt = stmt.where(_ilike_any(f.product, cast(v.affected_products, String)))
        if f.cwe:
            stmt = stmt.where(v.cwe_ids.any(f.cwe))
        stmt = _date_range(stmt, v.published_at, f)
        return await paginate(self.s, stmt, VULN_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_vuln(self, cve_id: str) -> SecurityVulnerability | None:
        return await self.s.scalar(
            select(SecurityVulnerability).where(SecurityVulnerability.cve_id == cve_id)
        )

    async def vuln_stats(self, since: datetime) -> dict[str, Any]:
        v = SecurityVulnerability
        by_sev = dict(
            (await self.s.execute(select(v.severity, func.count()).group_by(v.severity))).tuples().all()
        )
        recent = v.published_at >= since
        row = (
            await self.s.execute(
                select(
                    func.count(v.id),
                    func.count(v.id).filter(v.known_exploited.is_(True)),
                    func.count(v.id).filter(recent),
                    func.count(v.id).filter(recent, v.severity == Severity.CRITICAL),
                )
            )
        ).one()
        return {
            "total": row[0],
            "by_severity": {str(k): c for k, c in by_sev.items()},
            "known_exploited": row[1],
            "published_last_7d": row[2],
            "critical_last_7d": row[3],
        }

    # ------------------------------------------------------------ incidents
    async def list_incidents(self, f: IncidentFilters, now: datetime) -> tuple[Sequence[Incident], int]:
        stmt = select(Incident)
        if f.q:
            stmt = stmt.where(_ilike_any(f.q, Incident.title))
        if f.provider:
            stmt = stmt.where(func.lower(Incident.provider).in_([p.lower() for p in f.provider]))
        if f.status:
            stmt = stmt.where(Incident.status.in_(f.status))
        if f.active_only:
            stmt = stmt.where(incident_is_active(now))
        stmt = _date_range(stmt, Incident.started_at, f)
        return await paginate(self.s, stmt, INCIDENT_SORT.order_by(f.sort), f.paging.offset, f.page_size)

    async def get_incident(self, incident_id: uuid.UUID) -> Incident | None:
        return await self.s.get(Incident, incident_id)
