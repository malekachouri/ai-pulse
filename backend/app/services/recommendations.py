"""What to learn next: personalised, explained recommendations.

Only two kinds of things are ever recommended:
* items AI Pulse collected (with their original source links), and
* curated official documentation from app/ai/learning.py (never a generated URL).

Each recommendation says why it was picked, from signals the user can see and change:
- followed technologies, providers and repositories ("Because you follow vLLM");
- what they read or bookmarked, through shared keywords ("Because you bookmarked “…” (shared: kv cache, …)");
- their interests ("Matches your interest in RAG").
Rule-based and deterministic: nothing is generated, and an item with no personal reason is not recommended.
"""

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.learning import CATALOG
from app.ai.pipeline import RULES_VERSION
from app.ai.scoring import INTEREST_CATEGORIES
from app.models import AIAnalysis, Article, ArticleRead, Bookmark, Category, User, UserPreference
from app.models.enums import AnalysisKind
from app.schemas.recommendations import RecommendationsOut, RecommendedItem, RecommendedResource, Signals
from app.services.articles import ArticleService

CANDIDATE_WINDOW = timedelta(days=21)
HISTORY_WINDOW = timedelta(days=90)
CANDIDATE_POOL = 400
HISTORY_LIMIT = 60
MAX_PER_SOURCE = 3
MIN_SHARED_KEYWORDS = 2


def mentions(text: str, terms: list[str]) -> list[str]:
    """Terms that appear in `text` as whole words (so "go" does not match "google")."""
    low = text.lower()
    return [t for t in terms if t and re.search(rf"(?<![\w-]){re.escape(t.lower())}(?![\w-])", low)]


@dataclass
class _Seen:
    title: str
    how: str  # "read" | "bookmarked"
    keywords: set[str]
    categories: set[str] = field(default_factory=set)


class RecommendationService:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    async def _keywords(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, set[str]]:
        if not ids:
            return {}
        rows = await self.s.execute(
            select(AIAnalysis.article_id, AIAnalysis.output["keywords"]).where(
                AIAnalysis.article_id.in_(ids),
                AIAnalysis.kind == AnalysisKind.ENTITIES,
                AIAnalysis.prompt_version == RULES_VERSION,
            )
        )
        return {aid: {str(k).lower() for k in (kw or [])} for aid, kw in rows.tuples()}

    async def _history(self, user_id: uuid.UUID) -> dict[uuid.UUID, _Seen]:
        since = self.now - HISTORY_WINDOW
        bookmarked = (
            (
                await self.s.execute(
                    select(Article)
                    .join(Bookmark, Bookmark.article_id == Article.id)
                    .where(Bookmark.user_id == user_id, Bookmark.created_at >= since)
                    .order_by(Bookmark.created_at.desc())
                    .limit(HISTORY_LIMIT)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        read = (
            (
                await self.s.execute(
                    select(Article)
                    .join(ArticleRead, ArticleRead.article_id == Article.id)
                    .where(ArticleRead.user_id == user_id, ArticleRead.read_at >= since)
                    .order_by(ArticleRead.read_at.desc())
                    .limit(HISTORY_LIMIT)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        kws = await self._keywords([a.id for a in [*bookmarked, *read]])
        out: dict[uuid.UUID, _Seen] = {}
        for how, rows in (("bookmarked", bookmarked), ("read", read)):  # a bookmark is the stronger signal
            for a in rows:
                out.setdefault(
                    a.id, _Seen(a.title, how, kws.get(a.id, set()), {c.slug for c in a.categories})
                )
        return out

    async def for_user(self, user: User, limit: int = 12) -> RecommendationsOut:
        pref = await self.s.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
        followed = list(
            dict.fromkeys(
                [*(pref.followed_technologies if pref else []), *(pref.followed_providers if pref else []),
                 *(pref.followed_repositories if pref else [])]
            )
        )  # fmt: skip
        interests = list(pref.interests) if pref else []
        interest_cats = {c for i in interests for c in INTEREST_CATEGORIES.get(i, set())}
        history = await self._history(user.id)
        signals = Signals(
            followed=followed,
            interests=interests,
            read=sum(h.how == "read" for h in history.values()),
            bookmarked=sum(h.how == "bookmarked" for h in history.values()),
        )
        if not followed and not interest_cats and not history:
            return RecommendationsOut(
                items=[],
                resources=[],
                signals=signals,
                note="Follow technologies in Settings, or read and bookmark items, to get recommendations.",
            )

        names = {c.slug: c.name for c in await self.s.scalars(select(Category))}
        candidates = (
            (
                await self.s.execute(
                    select(Article)
                    .where(
                        Article.collected_at >= self.now - CANDIDATE_WINDOW,
                        Article.duplicate_of_id.is_(None),
                        Article.id.not_in(list(history)) if history else true(),
                    )
                    .order_by(Article.importance_score.desc().nulls_last(), Article.published_at.desc())
                    .limit(CANDIDATE_POOL)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        cand_kw = await self._keywords([a.id for a in candidates])

        scored: list[tuple[float, Article, list[str]]] = []
        for a in candidates:
            reasons: list[str] = []
            score = 0.0
            text = " ".join([a.title, a.description or "", " ".join(a.tags or [])])
            follows = mentions(text, followed)
            if follows:
                reasons.append("Because you follow " + " and ".join(follows[:2]))
                score += 3.0 * min(3, len(follows))
            best: tuple[float, _Seen, set[str]] | None = None
            for seen in history.values():
                shared = cand_kw.get(a.id, set()) & seen.keywords
                if len(shared) >= MIN_SHARED_KEYWORDS:
                    weight = len(shared) + (0.5 if seen.how == "bookmarked" else 0.0)
                    if best is None or weight > best[0]:
                        best = (weight, seen, shared)
            if best is not None:
                _, seen, shared = best
                reasons.append(
                    f"Because you {seen.how} “{seen.title[:90]}” (shared: {', '.join(sorted(shared)[:3])})"
                )
                score += 2.0 + 0.5 * min(4, len(shared))
            cats = {c.slug for c in a.categories} & interest_cats
            if cats:
                reasons.append("Matches your interest in " + ", ".join(names.get(c, c) for c in sorted(cats)))
                score += 1.0
            if not reasons:
                continue  # not personal: the regular feeds already rank by importance
            scored.append((score + (a.importance_score or 0) / 100, a, reasons))

        scored.sort(key=lambda t: t[0], reverse=True)
        per_source: Counter[uuid.UUID] = Counter()
        picked: list[tuple[float, Article, list[str]]] = []
        for item in scored:
            if per_source[item[1].source_id] >= MAX_PER_SOURCE:
                continue  # variety: one busy feed must not fill the list
            per_source[item[1].source_id] += 1
            picked.append(item)
            if len(picked) >= limit:
                break

        outs = await ArticleService(self.s).to_out([a for _, a, _ in picked], user)
        items = [
            RecommendedItem(article=o, reasons=r, score=round(sc, 2))
            for o, (sc, _, r) in zip(outs, picked, strict=True)
        ]
        return RecommendationsOut(
            items=items,
            resources=self._resources(followed, interest_cats, history, picked, names),
            signals=signals,
            note=None if items else "Nothing new matches your signals in the last 3 weeks.",
        )

    @staticmethod
    def _resources(
        followed: list[str],
        interest_cats: set[str],
        history: dict[uuid.UUID, _Seen],
        picked: list[tuple[float, Article, list[str]]],
        names: dict[str, str],
    ) -> list[RecommendedResource]:
        """Curated documentation only, each with the reason it is suggested."""
        out: dict[str, RecommendedResource] = {}

        def add(category: str, reason: str) -> None:
            for title, url in CATALOG.get(category, []):
                out.setdefault(url, RecommendedResource(title=title, url=url, reason=reason))

        for term in followed:  # a followed technology named in a curated title, or a catalog topic itself
            for cat, links in CATALOG.items():
                for title, url in links:
                    if term.lower() == cat or mentions(title, [term]):
                        reason = f"Because you follow {term}"
                        out.setdefault(url, RecommendedResource(title=title, url=url, reason=reason))
        for cat in sorted(interest_cats):
            add(cat, f"Matches your interest in {names.get(cat, cat)}")
        history_cats = Counter(c for h in history.values() for c in h.categories)
        for cat, n in history_cats.most_common(3):
            if n >= 2:
                add(cat, f"Because you read {n} items about {names.get(cat, cat)}")
        rec_cats = Counter(c.slug for _, a, _ in picked for c in a.categories)
        for cat, _ in rec_cats.most_common(2):
            add(cat, f"Background for your recommended {names.get(cat, cat)} items")
        return list(out.values())[:8]
