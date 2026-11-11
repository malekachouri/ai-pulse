"""Technology Watchlist: everything new about what the user follows, grouped per followed entry.

The watchlist reuses the existing preferences, so there is a single place to follow things:
* followed_technologies - models, frameworks and technologies ("vLLM", "Llama 4", "Kubernetes");
* followed_providers    - vendors ("OpenAI", "Meta"); their model releases are included by provider;
* followed_repositories - GitHub repositories ("owner/name"); their releases, bugs and issues by repository.

Matching is deterministic and explainable: a whole-word mention in the title, description or tags, the
release key of a followed repository, or the provider of a tracked model. Every item keeps its original
source link. New releases of followed entries are also notified (rule "watchlist" in app/alerts/engine.py).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIModel, AIModelRelease, Article, SoftwareBug, User, UserPreference
from app.models.enums import IssueState, ItemType, Severity
from app.schemas.watchlist import WatchEntryOut, WatchlistOut, WatchRelease
from app.services.articles import ArticleService
from app.services.recommendations import mentions

WINDOW = timedelta(days=30)
NEW_WINDOW = timedelta(days=7)
POOL_PER_TERM = 80
ITEMS_PER_ENTRY = 8
RELEASE_TYPES = (ItemType.MODEL_RELEASE, ItemType.TOOL, ItemType.GITHUB_REPO)


def repo_from_key(canonical_key: str | None) -> str | None:
    """ "gh-release:owner/name:v1.2" -> "owner/name"."""
    if canonical_key and canonical_key.startswith("gh-release:"):
        parts = canonical_key.split(":", 2)
        return parts[1] if len(parts) == 3 else None
    return None


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@dataclass
class _Entry:
    term: str
    kind: str  # technology | provider | repository
    articles: list[Article] = field(default_factory=list)


class WatchlistService:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    async def _matches(self, term: str, kind: str) -> list[Article]:
        since = self.now - WINDOW
        conds = [Article.title.ilike(_like(term)), Article.description.ilike(_like(term))]
        if kind == "repository":
            repo = term.lower()
            conds += [
                Article.canonical_key.like(f"gh-release:{repo}:%"),
                func.lower(Article.url).like(_like(f"github.com/{repo}/")),
            ]
        if kind == "provider":
            conds.append(
                Article.id.in_(
                    select(AIModelRelease.article_id)
                    .join(AIModel, AIModel.id == AIModelRelease.model_id)
                    .where(func.lower(AIModel.provider) == term.lower())
                )
            )
        rows = (
            (
                await self.s.execute(
                    select(Article)
                    .where(Article.collected_at >= since, Article.duplicate_of_id.is_(None), or_(*conds))
                    .order_by(Article.published_at.desc().nulls_last(), Article.collected_at.desc())
                    .limit(POOL_PER_TERM)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        if kind == "repository":  # matched structurally (key / URL) or by the full "owner/name"
            return list(rows)
        provider_ids: set[uuid.UUID] = set()
        if kind == "provider":
            provider_ids = set(
                await self.s.scalars(
                    select(AIModelRelease.article_id)
                    .join(AIModel, AIModel.id == AIModelRelease.model_id)
                    .where(
                        func.lower(AIModel.provider) == term.lower(), AIModelRelease.article_id.is_not(None)
                    )
                )
            )
        # ILIKE is a prefilter; keep whole-word mentions only ("Go" must not match "Google").
        return [
            a
            for a in rows
            if a.id in provider_ids
            or mentions(" ".join([a.title, a.description or "", " ".join(a.tags or [])]), [term])
        ]

    async def _open_critical_bugs(self, repo: str) -> int:
        return int(
            await self.s.scalar(
                select(func.count(SoftwareBug.id)).where(
                    func.lower(SoftwareBug.project) == repo.lower(),
                    SoftwareBug.status == IssueState.OPEN,
                    SoftwareBug.severity == Severity.CRITICAL,
                    SoftwareBug.severity_basis.is_not(None),
                )
            )
            or 0
        )

    @staticmethod
    def _release(arts: list[Article]) -> WatchRelease | None:
        for a in arts:  # newest first
            if a.item_type in RELEASE_TYPES:
                version = a.canonical_key.split(":", 2)[2] if repo_from_key(a.canonical_key) else None
                return WatchRelease(
                    article_id=str(a.id),
                    title=a.title,
                    url=a.url,
                    version=version,
                    published_at=a.published_at,
                    source=a.source.name,
                )
        return None

    async def for_user(self, user: User) -> WatchlistOut:
        pref = await self.s.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
        entries: list[_Entry] = []
        seen: set[str] = set()
        for kind, terms in (
            ("technology", pref.followed_technologies if pref else []),
            ("provider", pref.followed_providers if pref else []),
            ("repository", pref.followed_repositories if pref else []),
        ):
            for t in terms:
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    entries.append(_Entry(t, kind))
        if not entries:
            return WatchlistOut(
                entries=[],
                window_days=WINDOW.days,
                note="Follow technologies, providers or repositories in Settings to build your watchlist.",
            )

        for e in entries:
            e.articles = await self._matches(e.term, e.kind)
        shown = {a.id: a for e in entries for a in e.articles[:ITEMS_PER_ENTRY]}
        outs = {o.id: o for o in await ArticleService(self.s).to_out(list(shown.values()), user)}

        out: list[WatchEntryOut] = []
        new_since = self.now - NEW_WINDOW
        for e in entries:
            crit = await self._open_critical_bugs(e.term) if e.kind == "repository" else None
            out.append(
                WatchEntryOut(
                    term=e.term,
                    kind=e.kind,
                    total=len(e.articles),
                    new_this_week=sum(1 for a in e.articles if a.collected_at >= new_since),
                    latest_release=self._release(e.articles),
                    open_critical_bugs=crit,
                    vulnerabilities=sum(1 for a in e.articles if a.item_type == ItemType.VULNERABILITY),
                    items=[outs[a.id] for a in e.articles[:ITEMS_PER_ENTRY] if a.id in outs],
                )
            )
        # Entries with recent activity first, then the order the user followed them in.
        out.sort(key=lambda x: (x.new_this_week == 0, x.total == 0))
        return WatchlistOut(entries=out, window_days=WINDOW.days)
