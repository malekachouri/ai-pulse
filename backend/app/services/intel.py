"""Business logic for the typed intelligence modules: mapping, derived fields and not-found handling."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Incident, SoftwareBug
from app.repositories.intel import ACTIVE_INCIDENT_WINDOW, UNRESOLVED, IntelRepository
from app.schemas.common import Page
from app.schemas.intel import (
    AIModelDetail,
    AIModelOut,
    AIToolOut,
    BugFilters,
    GitHubIssueOut,
    GitHubRepositoryDetail,
    GitHubRepositoryOut,
    IncidentDetail,
    IncidentFilters,
    IncidentOut,
    IssueFilters,
    ModelFilters,
    ReleaseBrief,
    ReleaseFilters,
    ReleaseOut,
    RepoFilters,
    ResearchFilters,
    ResearchPaperOut,
    SecurityStats,
    SoftwareBugOut,
    ToolFilters,
    VulnerabilityDetail,
    VulnerabilityFilters,
    VulnerabilityOut,
)


def _now() -> datetime:
    return datetime.now(UTC)


def incident_flags(i: Incident, now: datetime) -> tuple[bool, bool]:
    """(is_active, status_is_stale). Never call something live without a fresh status-page check."""
    unresolved = i.status in UNRESOLVED
    fresh = i.last_verified_at >= now - ACTIVE_INCIDENT_WINDOW
    return unresolved and fresh, unresolved and not fresh


_BUG_FIELDS = (
    "id", "project", "kind", "severity", "severity_basis", "status", "affected_versions", "fixed_in_version",
    "fix_url", "source_url", "article_id", "created_at", "updated_at",
)  # fmt: skip


def bug_out(b: SoftwareBug) -> SoftwareBugOut:
    out = SoftwareBugOut.model_validate({**{k: getattr(b, k) for k in _BUG_FIELDS}, "title": b.project})
    issue, article = b.github_issue, b.article
    out.title = (article.title if article else None) or (issue.title if issue else None) or b.project
    if issue is not None:
        out.issue_number = issue.number
        out.repository = issue.repository.full_name
        out.labels = list(issue.labels)
        out.opened_at = issue.opened_at
        out.source_updated_at = issue.source_updated_at
    elif article is not None:
        out.opened_at = article.published_at
        out.source_updated_at = article.source_updated_at
    return out


class IntelService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = IntelRepository(session)

    # models
    async def list_models(self, f: ModelFilters) -> Page[AIModelOut]:
        rows, total = await self.repo.list_models(f)
        latest, counts = await self.repo.release_stats([m.id for m in rows])
        items = []
        for m in rows:
            out = AIModelOut.model_validate(m)
            rel = latest.get(m.id)
            out.latest_release = ReleaseBrief.model_validate(rel) if rel else None
            out.release_count = counts.get(m.id, 0)
            items.append(out)
        return Page.build(items, total, f.paging)

    async def get_model(self, model_id: uuid.UUID) -> AIModelDetail:
        m = await self.repo.get_model(model_id)
        if m is None:
            raise NotFoundError("Model not found")
        releases = sorted(
            m.releases,
            key=lambda r: r.released_at or r.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        out = AIModelDetail.model_validate(m)
        out.releases = [ReleaseBrief.model_validate(r) for r in releases]
        out.latest_release = out.releases[0] if out.releases else None
        out.release_count = len(out.releases)
        return out

    async def list_releases(self, f: ReleaseFilters) -> Page[ReleaseOut]:
        rows, total = await self.repo.list_releases(f)
        return Page.build([ReleaseOut.model_validate(r) for r in rows], total, f.paging)

    # tools
    async def list_tools(self, f: ToolFilters) -> Page[AIToolOut]:
        rows, total = await self.repo.list_tools(f)
        return Page.build([AIToolOut.model_validate(t) for t in rows], total, f.paging)

    async def get_tool(self, tool_id: uuid.UUID) -> AIToolOut:
        t = await self.repo.get_tool(tool_id)
        if t is None:
            raise NotFoundError("Tool not found")
        return AIToolOut.model_validate(t)

    # research
    async def list_papers(self, f: ResearchFilters) -> Page[ResearchPaperOut]:
        rows, total = await self.repo.list_papers(f)
        return Page.build([ResearchPaperOut.model_validate(p) for p in rows], total, f.paging)

    async def get_paper(self, key: str) -> ResearchPaperOut:
        p = await self.repo.get_paper(key)
        if p is None:
            raise NotFoundError("Paper not found")
        return ResearchPaperOut.model_validate(p)

    # GitHub
    async def list_repos(self, f: RepoFilters) -> Page[GitHubRepositoryOut]:
        rows, total = await self.repo.list_repos(f)
        return Page.build([GitHubRepositoryOut.model_validate(r) for r in rows], total, f.paging)

    async def get_repo(
        self, repo_id: uuid.UUID | None = None, full_name: str | None = None
    ) -> GitHubRepositoryDetail:
        r = await (self.repo.get_repo(repo_id) if repo_id else self.repo.get_repo_by_name(full_name or ""))
        if r is None:
            raise NotFoundError("Repository not found")
        return GitHubRepositoryDetail.model_validate(r)

    async def list_issues(self, f: IssueFilters) -> Page[GitHubIssueOut]:
        rows, total = await self.repo.list_issues(f)
        return Page.build([GitHubIssueOut.model_validate(i) for i in rows], total, f.paging)

    # bugs
    async def list_bugs(self, f: BugFilters) -> Page[SoftwareBugOut]:
        rows, total = await self.repo.list_bugs(f)
        return Page.build([bug_out(b) for b in rows], total, f.paging)

    async def get_bug(self, bug_id: uuid.UUID) -> SoftwareBugOut:
        b = await self.repo.get_bug(bug_id)
        if b is None:
            raise NotFoundError("Bug not found")
        return bug_out(b)

    # security
    async def list_vulns(self, f: VulnerabilityFilters) -> Page[VulnerabilityOut]:
        rows, total = await self.repo.list_vulns(f)
        return Page.build([VulnerabilityOut.model_validate(v) for v in rows], total, f.paging)

    async def get_vuln(self, cve_id: str) -> VulnerabilityDetail:
        v = await self.repo.get_vuln(cve_id)
        if v is None:
            raise NotFoundError(f"{cve_id} has not been collected")
        return VulnerabilityDetail.model_validate(v)

    async def vuln_stats(self) -> SecurityStats:
        return SecurityStats(**await self.repo.vuln_stats(_now() - timedelta(days=7)))

    # incidents
    def _incident(self, i: Incident, now: datetime, schema: type[IncidentOut] = IncidentOut) -> IncidentOut:
        out = schema.model_validate(i)
        out.is_active, out.status_is_stale = incident_flags(i, now)
        return out

    async def list_incidents(self, f: IncidentFilters) -> Page[IncidentOut]:
        now = _now()
        rows, total = await self.repo.list_incidents(f, now)
        return Page.build([self._incident(i, now) for i in rows], total, f.paging)

    async def get_incident(self, incident_id: uuid.UUID) -> IncidentDetail:
        i = await self.repo.get_incident(incident_id)
        if i is None:
            raise NotFoundError("Incident not found")
        out = self._incident(i, _now(), IncidentDetail)
        assert isinstance(out, IncidentDetail)
        return out
