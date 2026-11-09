"""Personalised daily briefing generation.

Sections are filled from collected items (never generated text), ranked by AI Pulse importance plus the
user's interests/followed technologies. Only the executive summary is LLM-written - from the selected items,
with citations, checked for unsupported claims. Without an LLM a deterministic summary is used. One briefing
per (user, date); regenerating replaces it.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import claims
from app.ai.learning import CATALOG
from app.ai.pipeline import record_usage
from app.ai.prompts import SYSTEM_BRIEFING, BriefingSummary
from app.ai.providers import AIProviders, ProviderError
from app.ai.scoring import personalize
from app.models import (
    AIAnalysis,
    Article,
    DailyBriefing,
    Incident,
    SecurityVulnerability,
    User,
    UserPreference,
)
from app.models.enums import AnalysisKind, BriefingFrequency, ItemType, NotificationKind, Severity

SECTIONS: list[tuple[str, list[ItemType], int]] = [
    ("top_ai", [ItemType.NEWS, ItemType.MODEL_RELEASE], 5),
    ("model_releases", [ItemType.MODEL_RELEASE], 5),
    ("new_tools", [ItemType.TOOL, ItemType.GITHUB_REPO], 5),
    ("research", [ItemType.RESEARCH], 5),
    ("bugs", [ItemType.BUG, ItemType.GITHUB_ISSUE], 5),
    ("vulnerabilities", [ItemType.VULNERABILITY], 5),
    ("incidents", [ItemType.INCIDENT], 5),
    ("devops", [ItemType.DEVOPS], 5),
]
MAX_PERIOD = timedelta(days=7)
WEEKLY_FACTOR = 2  # weekly briefings cover more ground, so each section lists more items
SECTION_LABEL = {
    "top_ai": "AI developments",
    "model_releases": "Model releases",
    "new_tools": "Tools & frameworks",
    "research": "Research papers",
    "bugs": "Important bugs",
    "vulnerabilities": "Critical vulnerabilities",
    "incidents": "Cloud & infrastructure incidents",
    "devops": "DevOps & cloud updates",
}


def local_now(pref: UserPreference | None, now: datetime) -> datetime:
    try:
        return now.astimezone(ZoneInfo(pref.timezone)) if pref else now
    except ZoneInfoNotFoundError:
        return now


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
                or_(
                    Article.published_at >= since,
                    # collected late but still recent; an old item backfilled today is not "new"
                    and_(
                        Article.collected_at >= since,
                        or_(Article.published_at.is_(None), Article.published_at >= self.now - MAX_PERIOD),
                    ),
                ),
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

    async def _incident_candidates(self, since: datetime, limit: int = 60) -> list[Article]:
        """Incidents that started or were resolved in the period, plus every one still unresolved."""
        stmt = (
            select(Article)
            .join(Incident, Incident.article_id == Article.id)
            .where(
                Article.duplicate_of_id.is_(None),
                or_(
                    Incident.started_at >= since,
                    Incident.resolved_at >= since,
                    Incident.resolved_at.is_(None) & (Incident.last_verified_at >= since),
                ),
            )
            .order_by(Article.importance_score.desc().nulls_last())
            .limit(limit)
        )
        return list((await self.s.scalars(stmt)).unique().all())

    async def generate(
        self, user: User | None, briefing_date: date | None = None, *, skip_if_exists: bool = False
    ) -> DailyBriefing:
        """Build (or rebuild) the briefing for the user's local date.

        Concurrent calls for the same (user, date) are serialised with a transaction-level advisory lock;
        with `skip_if_exists` (scheduled runs, retries) an existing briefing is returned untouched.
        """
        uid = user.id if user else None
        prefs = (
            await self.s.scalar(select(UserPreference).where(UserPreference.user_id == uid)) if uid else None
        )
        today = briefing_date or local_now(prefs, self.now).date()
        await self.s.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"briefing:{uid or 'global'}:{today}"}
        )
        existing = await self.s.scalar(
            select(DailyBriefing).where(
                DailyBriefing.user_id == uid if uid else DailyBriefing.user_id.is_(None),
                DailyBriefing.briefing_date == today,
            )
        )
        if existing is not None and skip_if_exists:
            return existing

        interests = list(prefs.interests) if prefs else []
        followed = [
            *(prefs.followed_technologies if prefs else []),
            *(prefs.followed_providers if prefs else []),
            *(prefs.followed_repositories if prefs else []),
        ]
        weekly = bool(prefs and prefs.briefing_frequency == BriefingFrequency.WEEKLY)
        prev = await self._previous(uid, today)
        default_span = timedelta(days=7) if weekly else timedelta(hours=24)
        start = max(prev.period_end if prev else self.now - default_span, self.now - MAX_PERIOD)
        if start >= self.now:
            start = self.now - default_span

        sections: dict[str, Any] = {}
        used: set[uuid.UUID] = set()
        all_items: list[tuple[Article, float, list[str]]] = []
        for key, types, n in SECTIONS:
            n = n * WEEKLY_FACTOR if weekly else n
            cands = (
                await self._incident_candidates(start)
                if key == "incidents"
                else await self._candidates(types, start)
            )
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
            if key == "bugs":  # no "important" label without a documented severity or a real importance score
                cands = [c for c in cands if c.severity_basis or (c.importance_score or 0) >= 50]
            ranked = []
            for a in cands:
                text_ = f"{a.title} {a.description or ''}"
                score, why = personalize(
                    a.importance_score or 0,
                    categories=[c.slug for c in a.categories],
                    text=text_,
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
        rendered: dict[str, Any] = {
            key: [self._item(a, score, why, summaries.get(a.id)) for a, score, why in items]
            for key, items in sections.items()
        }
        await self._enrich(rendered)
        rendered["changes"] = await self._changes(rendered, prev, followed)
        rendered["learning"] = self._learning(all_items, summaries)
        rendered["meta"] = {
            "interests": interests,
            "followed_count": len(followed),
            "frequency": prefs.briefing_frequency.value if prefs else "daily",
            "timezone": prefs.timezone if prefs else "UTC",
            "previous_briefing_date": prev.briefing_date.isoformat() if prev else None,
        }

        numbered = [(a, s) for a, s, _ in sorted(all_items, key=lambda x: x[1], reverse=True)][:15]
        executive, provider, model = await self._executive(numbered, rendered, uid)
        cited = list(dict.fromkeys(str(a.id) for a, _, _ in all_items))

        b = existing or DailyBriefing(id=uuid.uuid4(), user_id=uid, briefing_date=today)
        b.period_start, b.period_end, b.generated_at = start, self.now, self.now
        b.executive_summary, b.sections, b.cited_article_ids = executive, rendered, cited
        b.llm_provider, b.llm_model = provider, model
        if existing is None:
            self.s.add(b)
        await self.s.flush()
        return b

    async def _enrich(self, rendered: dict[str, Any]) -> None:
        """Add verified facts the reader needs: incident state, CVE id and exploitation status."""
        from app.services.radar import incident_state

        inc_ids = [uuid.UUID(i["article_id"]) for i in rendered.get("incidents", [])]
        if inc_ids:
            incs = {
                str(i.article_id): i
                for i in await self.s.scalars(select(Incident).where(Incident.article_id.in_(inc_ids)))
            }
            for item in rendered["incidents"]:
                inc = incs.get(item["article_id"])
                if inc:
                    item["provider"] = inc.provider
                    item["state"] = incident_state(inc, self.now)
                    item["status"] = inc.status.value
                    item["last_verified_at"] = inc.last_verified_at.isoformat()
        vul_ids = [uuid.UUID(i["article_id"]) for i in rendered.get("vulnerabilities", [])]
        if vul_ids:
            vulns = {
                str(v.article_id): v
                for v in await self.s.scalars(
                    select(SecurityVulnerability).where(SecurityVulnerability.article_id.in_(vul_ids))
                )
            }
            for item in rendered["vulnerabilities"]:
                v = vulns.get(item["article_id"])
                if v:
                    item["cve_id"] = v.cve_id
                    item["cvss"] = v.cvss_score
                    item["known_exploited"] = v.known_exploited

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
            "severity_basis": a.severity_basis,
            "summary": (summary or {}).get("short_summary"),
            "summary_is_ai": bool(summary),
        }

    async def _changes(
        self, rendered: dict[str, Any], prev: DailyBriefing | None, followed: list[str]
    ) -> list[dict[str, Any]]:
        """Factual differences with the previous briefing - computed, never generated."""
        out: list[dict[str, Any]] = []
        prev_ids = set(prev.cited_article_ids) if prev else set()
        prev_sections: dict[str, Any] = prev.sections if prev else {}
        for key, _, _ in SECTIONS:
            now_n, before_n = len(rendered.get(key, [])), len(prev_sections.get(key, []) or [])
            new = [i for i in rendered.get(key, []) if i["article_id"] not in prev_ids]
            if new or now_n != before_n:
                out.append(
                    {
                        "kind": "count",
                        "title": f"{SECTION_LABEL[key]}: {len(new)} new since the last briefing",
                        "summary": f"{now_n} item(s) now vs {before_n} previously."
                        if prev
                        else "First briefing.",
                        "article_id": None,
                        "url": None,
                    }
                )
        if prev:
            # Incidents that were active in the previous briefing and are now resolved.
            prev_incidents = prev_sections.get("incidents", []) or []
            was_active = {i["article_id"]: i for i in prev_incidents if i.get("state") == "current"}
            if was_active:
                from app.services.radar import incident_state

                for inc in await self.s.scalars(
                    select(Incident).where(Incident.article_id.in_([uuid.UUID(k) for k in was_active]))
                ):
                    if incident_state(inc, self.now) == "historical":
                        item = was_active[str(inc.article_id)]
                        out.append(
                            {
                                "kind": "resolved",
                                "title": f"Resolved: {inc.provider} - {inc.title}"[:300],
                                "summary": "Active in the previous briefing; now reported resolved"
                                + (f" at {inc.resolved_at:%Y-%m-%d %H:%M} UTC." if inc.resolved_at else "."),
                                "article_id": item["article_id"],
                                "url": inc.status_page_url,
                            }
                        )
            # CVEs listed previously that CISA has since added to the KEV catalog.
            not_kev = [
                i["article_id"]
                for i in prev_sections.get("vulnerabilities", []) or []
                if not i.get("known_exploited")
            ]
            if not_kev:
                for v in await self.s.scalars(
                    select(SecurityVulnerability).where(
                        SecurityVulnerability.article_id.in_([uuid.UUID(k) for k in not_kev]),
                        SecurityVulnerability.known_exploited.is_(True),
                    )
                ):
                    out.append(
                        {
                            "kind": "exploited",
                            "title": f"Now actively exploited: {v.cve_id}",
                            "summary": "Added to CISA KEV"
                            + (f" on {v.kev_date_added}." if v.kev_date_added else "."),
                            "article_id": str(v.article_id),
                            "url": f"https://nvd.nist.gov/vuln/detail/{v.cve_id}",
                        }
                    )
        flagged = [
            i
            for k, items in rendered.items()
            if isinstance(items, list) and k not in ("changes", "learning")
            for i in items
            if any(f.lower() in i.get("title", "").lower() for f in followed)
        ]
        seen: set[str] = set()
        for i in flagged:
            if i["article_id"] in seen or len(seen) >= 5:
                continue
            seen.add(i["article_id"])
            out.append(
                {
                    "kind": "followed",
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
        counts = {k: len(v) for k, v in rendered.items() if k in SECTION_LABEL}
        crit = [i for i in rendered.get("vulnerabilities", []) if i.get("severity") == "critical"]
        fallback = (
            f"{sum(counts.values())} highlighted items: {counts.get('top_ai', 0)} AI developments, "
            f"{counts.get('new_tools', 0)} tools, {counts.get('research', 0)} papers, "
            f"{counts.get('vulnerabilities', 0)} important vulnerabilities ({len(crit)} critical), "
            f"{counts.get('bugs', 0)} bugs, {counts.get('incidents', 0)} incidents and "
            f"{counts.get('devops', 0)} DevOps/cloud updates. "
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


@dataclass(frozen=True)
class DueBriefing:
    user_id: uuid.UUID | None  # None = the global briefing
    local_date: date


def is_due(pref: UserPreference, now: datetime) -> date | None:
    """The local date a briefing is due for, or None. A missed hour is caught up later the same local day."""
    if pref.briefing_frequency == BriefingFrequency.OFF:
        return None
    local = local_now(pref, now)
    if local.hour < pref.briefing_hour:
        return None
    if pref.briefing_frequency == BriefingFrequency.WEEKDAYS and local.weekday() >= 5:
        return None
    if pref.briefing_frequency == BriefingFrequency.WEEKLY and local.weekday() != pref.briefing_weekday:
        return None
    return local.date()


async def due_briefings(session: AsyncSession, now: datetime) -> list[DueBriefing]:
    """Briefings to generate now: users whose local delivery time has passed today (per frequency and
    weekday) and who have no briefing for that local date yet, plus the global one after 06:00 UTC."""
    out: list[DueBriefing] = []
    rows = (
        await session.execute(
            select(UserPreference)
            .join(User, User.id == UserPreference.user_id)
            .where(UserPreference.briefing_frequency != BriefingFrequency.OFF, User.is_active.is_(True))
        )
    ).scalars()
    for pref in rows:
        day = is_due(pref, now)
        if day is None:
            continue
        exists = await session.scalar(
            select(DailyBriefing.id).where(
                DailyBriefing.user_id == pref.user_id, DailyBriefing.briefing_date == day
            )
        )
        if exists is None:
            out.append(DueBriefing(pref.user_id, day))
    if (
        now.hour >= 6
        and await session.scalar(
            select(DailyBriefing.id).where(
                DailyBriefing.user_id.is_(None), DailyBriefing.briefing_date == now.date()
            )
        )
        is None
    ):
        out.append(DueBriefing(None, now.date()))
    return out


async def notify_briefing(session: AsyncSession, b: DailyBriefing, now: datetime) -> bool:
    """In-app "your briefing is ready" notification, once per (user, date), if the user wants it."""
    from app.alerts.engine import Event, deliver, settings_for

    if b.user_id is None:
        return False
    pref = await session.scalar(select(UserPreference).where(UserPreference.user_id == b.user_id))
    if not settings_for(pref).briefing_ready:
        return False
    counts = {k: len(v) for k, v in b.sections.items() if isinstance(v, list) and k in SECTION_LABEL}
    crit = sum(1 for i in b.sections.get("vulnerabilities", []) if i.get("severity") == "critical")
    label = "weekly" if pref and pref.briefing_frequency == BriefingFrequency.WEEKLY else "daily"
    body = (
        f"{sum(counts.values())} highlighted items"
        + (f", {crit} critical vulnerabilities" if crit else "")
        + (f", {counts.get('incidents', 0)} incidents" if counts.get("incidents") else "")
        + "."
    )
    return await deliver(
        session,
        b.user_id,
        Event(
            "briefing_ready",
            NotificationKind.BRIEFING,
            Severity.INFO,
            f"Your {label} briefing for {b.briefing_date:%a %d %b} is ready",
            body,
            f"/briefing?date={b.briefing_date.isoformat()}",
            None,
            f"briefing:{b.briefing_date.isoformat()}",
            {},
        ),
        now,
    )


async def run_scheduled_briefing(
    session: AsyncSession, providers: AIProviders, user_id: uuid.UUID | None, day: date, now: datetime
) -> tuple[DailyBriefing | None, bool]:
    """Generate one scheduled briefing (idempotent: an existing one is kept) and notify the user.

    Safe to retry: the briefing is unique per (user, date) and the notification per (user, dedup key).
    """
    user = await session.get(User, user_id) if user_id else None
    if user_id and (user is None or not user.is_active):
        return None, False
    b = await BriefingGenerator(session, providers, now).generate(user, day, skip_if_exists=True)
    notified = await notify_briefing(session, b, now)
    return b, notified
