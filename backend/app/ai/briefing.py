"""Personalised daily briefing generation.

Sections are filled from collected items (never generated text), ranked by AI Pulse importance plus the
user's interests/followed technologies. Only the executive summary is LLM-written - from the selected items,
with citations, checked for unsupported claims. Without an LLM a deterministic summary is used. One briefing
per (user, date); regenerating replaces it.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import claims
from app.ai.learning import CATALOG
from app.ai.pipeline import record_usage
from app.ai.prompts import SYSTEM_BRIEFING, BriefingSummary
from app.ai.providers import AIProviders, ProviderError
from app.ai.scoring import personalize
from app.models import AIAnalysis, Article, DailyBriefing, SecurityVulnerability, User, UserPreference
from app.models.enums import AnalysisKind, ItemType, Severity

SECTIONS: list[tuple[str, list[ItemType], int]] = [
    ("top_ai", [ItemType.NEWS, ItemType.MODEL_RELEASE], 5),
    ("model_releases", [ItemType.MODEL_RELEASE], 5),
    ("new_tools", [ItemType.TOOL, ItemType.GITHUB_REPO], 5),
    ("research", [ItemType.RESEARCH], 5),
    ("vulnerabilities", [ItemType.VULNERABILITY], 5),
    ("bugs", [ItemType.BUG, ItemType.GITHUB_ISSUE, ItemType.INCIDENT], 5),
    ("devops", [ItemType.DEVOPS], 5),
]
MAX_PERIOD = timedelta(days=7)
SECTION_LABEL = {
    "top_ai": "AI developments",
    "model_releases": "Model releases",
    "new_tools": "Tools & frameworks",
    "research": "Research papers",
    "vulnerabilities": "Critical vulnerabilities",
    "bugs": "Bugs & incidents",
    "devops": "DevOps & cloud",
}


class BriefingGenerator:
    def __init__(self, session: AsyncSession, providers: AIProviders, now: datetime | None = None) -> None:
        self.s = session
        self.p = providers
        self.now = now or datetime.now(UTC)

    async def _previous(self, user_id: uuid.UUID | None, before: date) -> DailyBriefing | None:
        cond = DailyBriefing.user_id == user_id if user_id else DailyBriefing.user_id.is_(None)
        return await self.s.scalar(
            select(DailyBriefing)
            .where(cond, DailyBriefing.briefing_date < before)
            .order_by(DailyBriefing.briefing_date.desc())
            .limit(1)
        )

    async def _candidates(self, types: list[ItemType], since: datetime, limit: int = 60) -> list[Article]:
        stmt = (
            select(Article)
            .where(
                Article.item_type.in_(types),
                Article.duplicate_of_id.is_(None),
                or_(Article.published_at >= since, Article.collected_at >= since),
            )
            .order_by(Article.importance_score.desc().nulls_last())
            .limit(limit)
        )
        return list((await self.s.scalars(stmt)).unique().all())

    async def _summaries(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
        rows = await self.s.execute(
            select(AIAnalysis.article_id, AIAnalysis.output).where(
                AIAnalysis.article_id.in_(ids),
                AIAnalysis.kind == AnalysisKind.SUMMARY,
                AIAnalysis.valid.is_(True),
            )
        )
        return dict(rows.tuples().all())

    async def generate(self, user: User | None, briefing_date: date | None = None) -> DailyBriefing:
        today = briefing_date or self.now.date()
        uid = user.id if user else None
        prefs = (
            await self.s.scalar(select(UserPreference).where(UserPreference.user_id == uid)) if uid else None
        )
        interests = list(prefs.interests) if prefs else []
        followed = [
            *(prefs.followed_technologies if prefs else []),
            *(prefs.followed_providers if prefs else []),
            *(prefs.followed_repositories if prefs else []),
        ]
        prev = await self._previous(uid, today)
        start = max(prev.period_end if prev else self.now - timedelta(hours=24), self.now - MAX_PERIOD)
        if start >= self.now:
            start = self.now - timedelta(hours=24)

        sections: dict[str, Any] = {}
        used: set[uuid.UUID] = set()
        all_items: list[tuple[Article, float, list[str]]] = []
        for key, types, n in SECTIONS:
            cands = await self._candidates(types, start)
            if key == "vulnerabilities":
                kev = set(
                    await self.s.scalars(
                        select(SecurityVulnerability.article_id).where(
                            SecurityVulnerability.known_exploited.is_(True),
                            SecurityVulnerability.article_id.in_([c.id for c in cands]),
                        )
                    )
                )
                cands = [c for c in cands if c.id in kev or c.severity in (Severity.CRITICAL, Severity.HIGH)]
            ranked = []
            for a in cands:
                text = f"{a.title} {a.description or ''}"
                score, why = personalize(
                    a.importance_score or 0,
                    categories=[c.slug for c in a.categories],
                    text=text,
                    interests=interests,
                    followed=followed,
                )
                ranked.append((a, score, why))
            ranked.sort(key=lambda x: x[1], reverse=True)
            picked = [r for r in ranked if r[0].id not in used][:n] if key != "model_releases" else ranked[:n]
            used.update(a.id for a, _, _ in picked)
            all_items.extend(picked)
            sections[key] = picked

        summaries = await self._summaries([a.id for a, _, _ in all_items])
        rendered = {
            key: [self._item(a, score, why, summaries.get(a.id)) for a, score, why in items]
            for key, items in sections.items()
        }
        rendered["changes"] = self._changes(rendered, prev, followed)
        rendered["learning"] = self._learning(all_items, summaries)

        numbered = [(a, s) for a, s, _ in sorted(all_items, key=lambda x: x[1], reverse=True)][:15]
        executive, provider, model = await self._executive(numbered, rendered, uid)
        cited = list(dict.fromkeys(str(a.id) for a, _, _ in all_items))

        existing = await self.s.scalar(
            select(DailyBriefing).where(
                DailyBriefing.user_id == uid if uid else DailyBriefing.user_id.is_(None),
                DailyBriefing.briefing_date == today,
            )
        )
        b = existing or DailyBriefing(id=uuid.uuid4(), user_id=uid, briefing_date=today)
        b.period_start, b.period_end, b.generated_at = start, self.now, self.now
        b.executive_summary, b.sections, b.cited_article_ids = executive, rendered, cited
        b.llm_provider, b.llm_model = provider, model
        if existing is None:
            self.s.add(b)
        await self.s.flush()
        return b

    def _item(
        self, a: Article, score: float, why: list[str], summary: dict[str, Any] | None
    ) -> dict[str, Any]:
        return {
            "article_id": str(a.id),
            "title": a.title,
            "url": a.url,
            "source": a.source.name,
            "item_type": a.item_type.value,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "importance": a.importance_score,
            "personal_score": score,
            "why_for_you": why,
            "severity": a.severity.value if a.severity else None,
            "summary": (summary or {}).get("short_summary"),
            "summary_is_ai": bool(summary),
        }

    def _changes(
        self, rendered: dict[str, Any], prev: DailyBriefing | None, followed: list[str]
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        prev_ids = set(prev.cited_article_ids) if prev else set()
        prev_sections = prev.sections if prev else {}
        for key, _, _ in SECTIONS:
            now_n, before_n = len(rendered.get(key, [])), len(prev_sections.get(key, []) or [])
            new = [i for i in rendered.get(key, []) if i["article_id"] not in prev_ids]
            if new or now_n != before_n:
                out.append(
                    {
                        "title": f"{SECTION_LABEL[key]}: {len(new)} new since the last briefing",
                        "summary": f"{now_n} item(s) now vs {before_n} previously."
                        if prev
                        else "First briefing.",
                        "article_id": None,
                        "url": None,
                    }
                )
        flagged = [
            i
            for items in rendered.values()
            if isinstance(items, list)
            for i in items
            if any(f.lower() in i.get("title", "").lower() for f in followed)
        ]
        for i in flagged[:5]:
            out.append(
                {
                    "title": f"Followed: {i['title']}",
                    "url": i["url"],
                    "article_id": i["article_id"],
                    "summary": "Mentions something you follow.",
                }
            )
        return out

    def _learning(
        self, items: list[tuple[Article, float, list[str]]], summaries: dict[uuid.UUID, Any]
    ) -> list[dict[str, Any]]:
        cats: dict[str, int] = {}
        for a, _, _ in items[:15]:
            for c in a.categories:
                cats[c.slug] = cats.get(c.slug, 0) + 1
        tasks: list[dict[str, Any]] = []
        for slug, _ in sorted(cats.items(), key=lambda kv: -kv[1])[:3]:
            for title, url in CATALOG.get(slug, [])[:1]:
                tasks.append(
                    {
                        "title": f"Study: {title}",
                        "url": url,
                        "summary": f"Several of today's items concern {slug}.",
                        "article_id": None,
                        "source": "curated",
                    }
                )
        for a, _, _ in items[:10]:
            for topic in (summaries.get(a.id) or {}).get("learning_resources", []):
                if topic.get("source") == "ai-suggested topic" and len(tasks) < 6:
                    tasks.append(
                        {
                            "title": f"Explore: {topic['title']}",
                            "url": None,
                            "article_id": str(a.id),
                            "summary": f"Suggested by AI from “{a.title[:80]}”.",
                            "source": "ai-suggested",
                        }
                    )
        return tasks

    async def _executive(
        self, numbered: list[tuple[Article, float]], rendered: dict[str, Any], uid: uuid.UUID | None
    ) -> tuple[str, str | None, str | None]:
        if not numbered:
            return "No new items were collected for this period.", None, None
        counts = {
            k: len(v) for k, v in rendered.items() if isinstance(v, list) and k not in ("changes", "learning")
        }
        crit = [i for i in rendered.get("vulnerabilities", []) if i.get("severity") == "critical"]
        fallback = (
            f"{sum(counts.values())} highlighted items: {counts.get('top_ai', 0)} AI developments, "
            f"{counts.get('new_tools', 0)} tools, {counts.get('research', 0)} papers, "
            f"{counts.get('vulnerabilities', 0)} important vulnerabilities ({len(crit)} critical), "
            f"{counts.get('bugs', 0)} bugs/incidents and {counts.get('devops', 0)} DevOps/cloud updates. "
            f"Top item: {numbered[0][0].title}."
        )
        llm = self.p.llm
        if llm is None:
            return fallback, None, None
        listing = "\n".join(
            f"[{i + 1}] ({a.item_type.value}, importance {a.importance_score}) {a.title} — "
            f"{(a.description or '')[:300]}"
            for i, (a, _) in enumerate(numbered)
        )
        try:
            result = await llm.complete_json(
                SYSTEM_BRIEFING, f"ITEMS:\n{listing}\n\nWrite the executive summary.", BriefingSummary
            )
        except ProviderError as exc:
            await record_usage(
                self.s, "briefing", llm.provider, llm.model, ok=False, error=str(exc), user_id=uid
            )
            return fallback, None, None
        await record_usage(
            self.s,
            "briefing",
            llm.provider,
            llm.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost=result.cost_usd,
            user_id=uid,
        )
        text, _bad = claims.strip_unsupported(result.data.executive_summary, listing)
        return (text or fallback), (result.provider if text else None), (result.model if text else None)


async def due_briefings(session: AsyncSession, now: datetime) -> list[uuid.UUID | None]:
    """Users whose local delivery hour is now and who have no briefing for their local date yet.
    `None` = the global briefing (generated once a day after 06:00 UTC)."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from app.models.enums import BriefingFrequency

    out: list[uuid.UUID | None] = []
    rows = (
        await session.execute(
            select(UserPreference, User.is_active)
            .join(User, User.id == UserPreference.user_id)
            .where(UserPreference.briefing_frequency != BriefingFrequency.OFF)
        )
    ).all()
    for pref, active in rows:
        if not active:
            continue
        try:
            local = now.astimezone(ZoneInfo(pref.timezone))
        except ZoneInfoNotFoundError:
            local = now
        if local.hour != pref.briefing_hour:
            continue
        if pref.briefing_frequency == BriefingFrequency.WEEKDAYS and local.weekday() >= 5:
            continue
        if pref.briefing_frequency == BriefingFrequency.WEEKLY and local.weekday() != 0:
            continue
        exists = await session.scalar(
            select(DailyBriefing.id).where(
                DailyBriefing.user_id == pref.user_id, DailyBriefing.briefing_date == local.date()
            )
        )
        if exists is None:
            out.append(pref.user_id)
    if (
        now.hour >= 6
        and await session.scalar(
            select(DailyBriefing.id).where(
                DailyBriefing.user_id.is_(None), DailyBriefing.briefing_date == now.date()
            )
        )
        is None
    ):
        out.append(None)
    return out
