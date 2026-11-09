"""Persists normalized items idempotently.

* Articles upsert on (source_id, external_id); an unchanged content hash is a no-op ("skipped").
* A new article whose canonical key (CVE id, arXiv id, or canonical URL) already exists from another
  source is stored but linked via `duplicate_of_id`, so feeds show it once.
* Typed rows (CVEs, incidents, papers, releases, repos, tools, issues, bugs) upsert on natural keys with
  INSERT … ON CONFLICT DO NOTHING + row lock, so concurrent workers can't create duplicates. Merges never
  replace a known value with an unknown (None) one.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.normalized import NormalizedItem
from app.ingestion.text import canonical_url
from app.models import (
    AIModel,
    AIModelRelease,
    AITool,
    Article,
    Category,
    GitHubIssue,
    GitHubRepository,
    Incident,
    ResearchPaper,
    SecurityVulnerability,
    SoftwareBug,
    Source,
)
from app.models.enums import Severity

STAR_HISTORY_DAYS = 60


@dataclass
class SaveStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    created_ids: list[uuid.UUID] = field(default_factory=list)


def _set_known(obj: Any, values: dict[str, Any]) -> bool:
    """Assign only non-None values; return True if anything changed."""
    changed = False
    for key, value in values.items():
        if value is not None and getattr(obj, key) != value:
            setattr(obj, key, value)
            changed = True
    return changed


def _merge_unique(existing: list[Any] | None, incoming: list[Any] | None, limit: int = 300) -> list[Any]:
    out = list(existing or [])
    seen = {json.dumps(x, sort_keys=True, default=str) for x in out}
    for x in incoming or []:
        k = json.dumps(x, sort_keys=True, default=str)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out[:limit]


class ItemWriter:
    def __init__(self, session: AsyncSession, source: Source, now: datetime) -> None:
        self.s = session
        self.source = source
        self.now = now
        self._categories: dict[str, Category] | None = None

    async def _category_map(self) -> dict[str, Category]:
        if self._categories is None:
            self._categories = {c.slug: c for c in await self.s.scalars(select(Category))}
        return self._categories

    async def _get_or_create(self, model: Any, keys: dict[str, Any], defaults: dict[str, Any]) -> Any:
        values = {**defaults, **keys}
        if "id" in model.__table__.c and "id" not in values:
            values["id"] = uuid.uuid4()
        # Flush first: populate_existing below would otherwise discard pending in-session changes to this row.
        await self.s.flush()
        await self.s.execute(insert(model).values(**values).on_conflict_do_nothing())
        stmt = (
            select(model)
            .filter_by(**keys)
            .with_for_update(of=model)
            .execution_options(populate_existing=True)
        )
        return (await self.s.scalars(stmt)).one()

    # ------------------------------------------------------------------ articles
    async def save(self, items: list[NormalizedItem]) -> SaveStats:
        stats = SaveStats()
        for item in items:
            article: Article | None = None
            if item.create_article:
                article, outcome = await self._save_article(item)
                setattr(stats, outcome, getattr(stats, outcome) + 1)
                if outcome == "created":
                    stats.created_ids.append(article.id)
            changed = await self._save_typed(item, article.id if article else None)
            if not item.create_article:  # typed-only record: count it as updated or unchanged
                stats.updated += int(changed)
                stats.skipped += int(not changed)
        await self.s.flush()
        return stats

    async def _save_article(self, item: NormalizedItem) -> tuple[Article, str]:
        h = item.content_hash()
        cats = await self._category_map()
        categories = [cats[c] for c in item.categories if c in cats]
        canonical = item.canonical_key or f"url:{canonical_url(item.url)}"
        existing = await self.s.scalar(
            select(Article).where(
                Article.source_id == self.source.id, Article.external_id == item.external_id
            )
        )
        fields = dict(
            item_type=item.item_type,
            title=item.title[:1000],
            description=item.description,
            content=item.content,
            url=item.url,
            author=item.author,
            language=item.language,
            published_at=item.published_at,
            source_updated_at=item.source_updated_at,
            verification_status=item.verification,
            severity=item.severity,
            severity_basis=item.severity_basis,
            tags=item.tags[:30],
            raw=item.raw,
            canonical_key=canonical,
        )
        if existing is not None:
            if existing.content_hash == h:
                return existing, "skipped"
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.content_hash = h
            existing.categories = categories
            if existing.source_updated_at is None:
                existing.source_updated_at = self.now  # we observed a change; the source gave no timestamp
            return existing, "updated"

        primary = await self.s.scalar(
            select(Article.id)
            .where(
                Article.canonical_key == canonical,
                Article.source_id != self.source.id,
                Article.duplicate_of_id.is_(None),
            )
            .order_by(Article.collected_at)
            .limit(1)
        )
        article = Article(
            id=uuid.uuid4(),
            source_id=self.source.id,
            external_id=item.external_id,
            collected_at=self.now,
            content_hash=h,
            duplicate_of_id=primary,
            categories=categories,
            **fields,
        )
        self.s.add(article)
        await self.s.flush()
        return article, "created"

    # ------------------------------------------------------------------ typed tables
    async def _save_typed(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        changed = False
        if item.vulnerability:
            changed |= await self._vulnerability(item, article_id)
        if item.incident:
            changed |= await self._incident(item, article_id)
        if item.paper:
            changed |= await self._paper(item, article_id)
        if item.release:
            changed |= await self._release(item, article_id)
        if item.repository:
            changed |= await self._repository(item)
        if item.tool:
            changed |= await self._tool(item, article_id)
        if item.issue:
            changed |= await self._issue(item, article_id)
        return changed

    async def _vulnerability(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.vulnerability
        assert p is not None
        v: SecurityVulnerability = await self._get_or_create(
            SecurityVulnerability, {"cve_id": p.cve_id}, {"severity": p.severity or Severity.UNKNOWN}
        )
        before = json.dumps(
            [
                v.cvss_score,
                v.severity,
                v.known_exploited,
                v.remediation,
                v.references,
                v.affected_products,
                v.last_modified_at,
                v.patch_available,
                v.cwe_ids,
                v.kev_date_added,
            ],
            default=str,
        )
        _set_known(
            v,
            {
                "description": p.description,
                "cvss_score": p.cvss_score,
                "cvss_version": p.cvss_version,
                "cvss_vector": p.cvss_vector,
                "kev_date_added": p.kev_date_added,
                "kev_due_date": p.kev_due_date,
                "published_at": p.published_at,
                "last_modified_at": p.last_modified_at,
            },
        )
        if p.severity and p.severity != Severity.UNKNOWN:
            v.severity = p.severity
        if p.known_exploited:  # only ever set True; absence of evidence is not evidence of absence
            v.known_exploited = True
        if p.patch_available:
            v.patch_available = True
        if p.remediation and (not v.remediation or p.known_exploited):
            v.remediation = p.remediation
        v.references = _merge_unique(v.references, p.references)
        v.affected_products = _merge_unique(v.affected_products, p.affected_products)
        v.cwe_ids = list(dict.fromkeys([*(v.cwe_ids or []), *(p.cwe_ids or [])]))
        if v.article_id is None and article_id is not None:
            v.article_id = article_id
        v.last_verified_at = self.now  # just re-read from an official source
        after = json.dumps(
            [
                v.cvss_score,
                v.severity,
                v.known_exploited,
                v.remediation,
                v.references,
                v.affected_products,
                v.last_modified_at,
                v.patch_available,
                v.cwe_ids,
                v.kev_date_added,
            ],
            default=str,
        )
        return before != after

    async def _incident(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.incident
        assert p is not None
        i: Incident = await self._get_or_create(
            Incident,
            {"provider": p.provider, "external_id": p.external_id},
            {
                "title": p.title,
                "status": p.status,
                "status_page_url": p.status_page_url,
                "last_verified_at": self.now,
            },
        )
        changed = _set_known(
            i,
            {
                "title": p.title,
                "status": p.status,
                "status_page_url": p.status_page_url,
                "impact": p.impact,
                "started_at": p.started_at,
                "resolved_at": p.resolved_at,
            },
        )
        i.affected_services = p.affected_services or i.affected_services
        i.regions = p.regions or i.regions
        if p.updates:
            i.updates = p.updates
        i.last_verified_at = self.now  # we just read the provider's own status data
        if i.article_id is None and article_id is not None:
            i.article_id = article_id
        return changed

    async def _paper(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.paper
        assert p is not None
        if not p.arxiv_id:
            return False
        paper: ResearchPaper = await self._get_or_create(
            ResearchPaper, {"arxiv_id": p.arxiv_id}, {"title": p.title}
        )
        changed = _set_known(
            paper,
            {
                "title": p.title,
                "abstract": p.abstract,
                "primary_category": p.primary_category,
                "pdf_url": p.pdf_url,
                "published_at": p.published_at,
                "doi": p.doi,
            },
        )
        if p.authors and paper.authors != p.authors:
            paper.authors, changed = p.authors, True
        if paper.article_id is None and article_id is not None:
            paper.article_id = article_id
        return changed

    async def _release(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.release
        assert p is not None
        model: AIModel = await self._get_or_create(
            AIModel, {"provider": p.provider, "name": p.model_name}, {"modality": p.modality or []}
        )
        _set_known(
            model, {"family": p.family, "is_open_weights": p.is_open_weights, "homepage_url": p.homepage_url}
        )
        if p.modality:
            model.modality = p.modality
        stmt = select(AIModelRelease).where(AIModelRelease.model_id == model.id)
        stmt = stmt.where(
            AIModelRelease.version == p.version if p.version else AIModelRelease.source_url == p.source_url
        )
        rel = await self.s.scalar(stmt)
        if rel is None:
            self.s.add(
                AIModelRelease(
                    id=uuid.uuid4(),
                    model_id=model.id,
                    version=p.version,
                    released_at=p.released_at,
                    source_url=p.source_url,
                    article_id=article_id,
                )
            )
            return True
        return _set_known(rel, {"released_at": p.released_at, "source_url": p.source_url})

    async def _repository(self, item: NormalizedItem) -> bool:
        p = item.repository
        assert p is not None
        repo: GitHubRepository = await self._get_or_create(
            GitHubRepository, {"full_name": p.full_name}, {"html_url": p.html_url}
        )
        changed = _set_known(
            repo,
            {
                "html_url": p.html_url,
                "github_id": p.github_id,
                "description": p.description,
                "language": p.language,
                "stars": p.stars,
                "forks": p.forks,
                "open_issues": p.open_issues,
                "pushed_at": p.pushed_at,
            },
        )
        if p.latest_release and (
            repo.latest_release_at is None
            or (p.latest_release_at and p.latest_release_at >= repo.latest_release_at)
        ):  # never let an older release overwrite the newest one
            repo.latest_release, repo.latest_release_at = p.latest_release, p.latest_release_at
            changed = True
        if p.topics is not None:
            repo.topics = p.topics
        if p.stars is not None:
            self._record_stars(repo, p.stars)
        return changed

    def _record_stars(self, repo: GitHubRepository, stars: int) -> None:
        """Daily star snapshots → stars gained over 7 days. GitHub has no trending API; this is our proxy."""
        today = self.now.date().isoformat()
        history = [h for h in (repo.star_history or []) if h.get("date") != today]
        history.append({"date": today, "stars": stars})
        history.sort(key=lambda h: h["date"])
        repo.star_history = history[-STAR_HISTORY_DAYS:]
        cutoff = (self.now - timedelta(days=7)).date().isoformat()
        older = [h for h in repo.star_history if h["date"] <= cutoff]
        repo.stars_delta_7d = stars - older[-1]["stars"] if older else None

    async def _tool(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.tool
        assert p is not None
        tool: AITool = await self._get_or_create(AITool, {"name": p.name}, {})
        repo_id = None
        if p.repository:
            repo = await self._get_or_create(
                GitHubRepository,
                {"full_name": p.repository},
                {"html_url": f"https://github.com/{p.repository}"},
            )
            repo_id = repo.id
        changed = _set_known(
            tool,
            {
                "description": p.description,
                "category": p.category,
                "homepage_url": p.homepage_url,
                "latest_version": p.latest_version,
                "license": p.license,
                "repository_id": repo_id,
            },
        )
        if article_id is not None:
            tool.article_id = article_id
        return changed

    async def _issue(self, item: NormalizedItem, article_id: uuid.UUID | None) -> bool:
        p = item.issue
        assert p is not None
        repo: GitHubRepository = await self._get_or_create(
            GitHubRepository, {"full_name": p.repository}, {"html_url": f"https://github.com/{p.repository}"}
        )
        issue: GitHubIssue = await self._get_or_create(
            GitHubIssue,
            {"repository_id": repo.id, "number": p.number},
            {"title": p.title, "html_url": p.html_url, "state": p.state, "opened_at": p.opened_at},
        )
        changed = _set_known(
            issue,
            {
                "title": p.title,
                "html_url": p.html_url,
                "state": p.state,
                "is_pull_request": p.is_pull_request,
                "comments": p.comments,
                "opened_at": p.opened_at,
                "source_updated_at": p.source_updated_at,
            },
        )
        issue.closed_at = p.closed_at
        issue.labels = p.labels
        if issue.article_id is None and article_id is not None:
            issue.article_id = article_id
        b = item.bug
        if b is not None:
            bug: SoftwareBug = await self._get_or_create(
                SoftwareBug,
                {"github_issue_id": issue.id},
                {
                    "project": b.project,
                    "kind": b.kind,
                    "severity": b.severity,
                    "status": b.status,
                    "source_url": b.source_url,
                },
            )
            changed |= _set_known(
                bug,
                {
                    "kind": b.kind,
                    "severity": b.severity,
                    "severity_basis": b.severity_basis,
                    "status": b.status,
                    "fixed_in_version": b.fixed_in_version,
                    "fix_url": b.fix_url,
                    "source_url": b.source_url,
                },
            )
            changed |= _set_known(bug, {"resolution": b.resolution, "fix_merged_at": b.fix_merged_at})
            bug.last_verified_at = self.now
            if b.affected_versions:
                bug.affected_versions = b.affected_versions
            if bug.article_id is None and article_id is not None:
                bug.article_id = article_id
        return changed
