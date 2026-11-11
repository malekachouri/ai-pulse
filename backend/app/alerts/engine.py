"""Alert engine: turns newly collected facts into per-user notifications.

Rules (each can be switched off and tuned per user in `user_preferences.alert_settings`):
  critical_cves  - new CVE with severity *critical* and a documented basis (NVD/vendor/K8s SRC); optional min CVSS
  exploited      - CVE added to CISA KEV in the last 2 days (always delivered as critical)
  critical_bugs  - new open bug labelled critical by the project (label = basis); optional repository filter
  outages        - incident that is *active* (unresolved per provider AND verified < 2 h ago) with provider impact
                   at or above the chosen level; optional provider filter. Unknown impact only passes "minor".
  watched_tech   - new CVE mentioning a followed technology/provider, at or above the user's severity threshold
  model_releases - new release (published in the last 7 days) of a model from `model_providers`, or from the
                   followed providers when that list is empty, or from any tracked provider when both are empty
  briefing_ready - a scheduled briefing was generated (sent by app.ai.briefing, not by this engine)
Delivery is idempotent: one notification per (user, dedup_key); a CVE yields at most one "new CVE" alert.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    AIModel,
    AIModelRelease,
    Article,
    Incident,
    Notification,
    SecurityVulnerability,
    SoftwareBug,
    User,
    UserPreference,
)
from app.models.enums import IssueState, NotificationKind, Severity
from app.repositories.intel import incident_is_active

log = get_logger(__name__)
LOOKBACK = timedelta(hours=48)
DEFAULT_MIN_CVSS = 9.5
RELEASE_MAX_AGE = timedelta(days=7)  # backfilled old releases never notify
SEVERITY_RANK = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
    Severity.UNKNOWN: 0,
}
IMPACT_RANK = {"minor": 1, "major": 2, "critical": 3}
GCP_IMPACT = {"SERVICE_OUTAGE": "critical", "SERVICE_DISRUPTION": "major", "SERVICE_INFORMATION": "minor"}


class AlertSettings(BaseModel):
    critical_cves: bool = True
    exploited: bool = True
    critical_bugs: bool = True
    outages: bool = True
    watched_tech: bool = True
    # Default 9.5: NVD publishes ~40 critical CVEs a day; alerting on all of them drowned the rest
    # (84 per user in 48 h on live data, 56 with 9.5). Users can choose "any critical" (null) or stricter.
    min_cvss: float | None = Field(
        DEFAULT_MIN_CVSS, ge=0, le=10, description="Only alert on critical CVEs with CVSS >= this"
    )
    outage_min_impact: Literal["minor", "major", "critical"] = "major"
    outage_providers: list[str] = Field(
        default_factory=list, max_length=30, description="Empty = all providers"
    )
    bug_projects: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="owner/name; empty = followed repositories, or all if none",
    )
    model_releases: bool = True
    model_providers: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Empty = followed providers, or every tracked provider if none is followed",
    )
    briefing_ready: bool = True


def settings_for(pref: UserPreference | None) -> AlertSettings:
    return AlertSettings.model_validate(
        {**AlertSettings().model_dump(), **((pref.alert_settings if pref else None) or {})}
    )


def incident_impact(i: Incident) -> str | None:
    if i.impact in IMPACT_RANK:
        return i.impact
    return GCP_IMPACT.get(i.impact or "")


def _mentions(text: str, terms: list[str]) -> list[str]:
    low = text.lower()
    return [t for t in terms if t and re.search(rf"(?<![\w-]){re.escape(t.lower())}(?![\w-])", low)]


@dataclass
class AlertStats:
    candidates: int = 0
    created: int = 0
    by_rule: dict[str, int] = field(default_factory=dict)


@dataclass
class Event:
    rule: str
    kind: NotificationKind
    severity: Severity
    title: str
    body: str | None
    link: str | None
    article_id: uuid.UUID | None
    dedup_key: str
    facts: dict[str, Any]


async def deliver(session: AsyncSession, user_id: uuid.UUID, e: Event, now: datetime) -> bool:
    """Insert one in-app notification. Returns False when (user, dedup_key) was already notified."""
    res = await session.execute(
        insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            kind=e.kind,
            severity=e.severity,
            title=e.title[:500],
            body=e.body,
            article_id=e.article_id,
            link=e.link,
            dedup_key=e.dedup_key[:200],
            created_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_notifications_user_dedup")
    )
    return bool(res.rowcount)  # type: ignore[attr-defined]


class AlertEngine:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    async def _articles(self, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, Article]:
        real = [i for i in ids if i]
        if not real:
            return {}
        return {a.id: a for a in (await self.s.scalars(select(Article).where(Article.id.in_(real)))).unique()}

    async def collect(self) -> dict[str, list[Event]]:
        since = self.now - LOOKBACK
        V = SecurityVulnerability  # noqa: N806
        vulns = (
            await self.s.scalars(
                select(V).where(
                    or_(V.published_at >= since, V.kev_date_added >= (self.now - timedelta(days=2)).date())
                )
            )
        ).all()
        arts = await self._articles([v.article_id for v in vulns])
        out: dict[str, list[Event]] = {"vuln": [], "kev": [], "bug": [], "outage": [], "model": []}
        for v in vulns:
            a = arts.get(v.article_id) if v.article_id else None
            link = a.url if a else f"https://nvd.nist.gov/vuln/detail/{v.cve_id}"
            basis = a.severity_basis if a else None
            text = " ".join(
                [
                    v.cve_id,
                    v.description or "",
                    a.title if a else "",
                    " ".join(
                        f"{p.get('vendor', '')} {p.get('product', '')}" for p in v.affected_products or []
                    ),
                ]
            )
            if v.published_at and v.published_at >= since:
                cvss = f" (CVSS {v.cvss_score})" if v.cvss_score is not None else ""
                out["vuln"].append(
                    Event(
                        "cve",
                        NotificationKind.VULNERABILITY,
                        v.severity,
                        f"New {v.severity.value} CVE: {v.cve_id}{cvss}",
                        (
                            (v.description or "")[:280] + (f" — Severity basis: {basis}" if basis else "")
                        ).strip(),
                        link,
                        v.article_id,
                        f"cve:{v.cve_id}:new",
                        {
                            "cvss": v.cvss_score,
                            "has_basis": bool(basis) or v.cvss_score is not None,
                            "text": text,
                        },
                    )
                )
            if (
                v.known_exploited
                and v.kev_date_added
                and v.kev_date_added >= (self.now - timedelta(days=2)).date()
            ):
                out["kev"].append(
                    Event(
                        "exploited",
                        NotificationKind.CRITICAL_ALERT,
                        Severity.CRITICAL,
                        f"Actively exploited: {v.cve_id} added to CISA KEV",
                        (v.remediation or "")[:300]
                        + (f" Due date: {v.kev_due_date}." if v.kev_due_date else ""),
                        link,
                        v.article_id,
                        f"cve:{v.cve_id}:kev",
                        {"text": text},
                    )
                )

        bugs = (
            (
                await self.s.scalars(
                    select(SoftwareBug).where(
                        SoftwareBug.created_at >= since,
                        SoftwareBug.status == IssueState.OPEN,
                        SoftwareBug.severity == Severity.CRITICAL,
                        SoftwareBug.severity_basis.is_not(None),
                    )
                )
            )
            .unique()
            .all()
        )
        for b in bugs:
            title = b.github_issue.title if b.github_issue else b.project
            out["bug"].append(
                Event(
                    "critical_bug",
                    NotificationKind.BUG,
                    Severity.CRITICAL,
                    f"Critical bug in {b.project}: {title}"[:480],
                    f"Severity basis: {b.severity_basis}.",
                    b.source_url,
                    b.article_id,
                    f"bug:{b.id}",
                    {"project": b.project},
                )
            )

        releases = (
            await self.s.execute(
                select(AIModelRelease, AIModel)
                .join(AIModel, AIModel.id == AIModelRelease.model_id)
                .where(
                    AIModelRelease.created_at >= since,
                    or_(
                        AIModelRelease.released_at.is_(None),
                        AIModelRelease.released_at >= self.now - RELEASE_MAX_AGE,
                    ),
                )
            )
        ).all()
        for r, m in releases:
            name = f"{m.name}{f' {r.version}' if r.version and r.version not in m.name else ''}"
            out["model"].append(
                Event(
                    "model_release",
                    NotificationKind.MODEL_RELEASE,
                    Severity.INFO,
                    f"New model release from {m.provider}: {name}"[:480],
                    (r.notes or "")[:280] or None,
                    r.source_url,
                    r.article_id,
                    f"model:{r.id}",
                    {"provider": m.provider},
                )
            )

        incidents = (await self.s.scalars(select(Incident).where(incident_is_active(self.now)))).all()
        for i in incidents:
            impact = incident_impact(i)
            out["outage"].append(
                Event(
                    "outage",
                    NotificationKind.INCIDENT,
                    Severity.CRITICAL if impact == "critical" else Severity.HIGH,
                    f"{i.provider} incident: {i.title}"[:480],
                    f"Status: {i.status.value} (verified {i.last_verified_at:%H:%M} UTC)"
                    + (f"; impact: {impact}" if impact else "")
                    + (f"; services: {', '.join(i.affected_services[:5])}" if i.affected_services else ""),
                    i.status_page_url,
                    i.article_id,
                    f"incident:{i.id}",
                    {"provider": i.provider, "impact": impact},
                )
            )
        return out

    def for_user(
        self,
        events: dict[str, list[Event]],
        s: AlertSettings,
        min_sev: Severity,
        followed: list[str],
        repos: list[str],
        providers_followed: list[str] | None = None,
    ) -> list[Event]:
        picked: dict[str, Event] = {}
        floor = SEVERITY_RANK[min_sev]
        for e in events["vuln"]:
            facts = e.facts
            if (
                s.critical_cves
                and e.severity == Severity.CRITICAL
                and facts["has_basis"]
                and (s.min_cvss is None or (facts["cvss"] is not None and facts["cvss"] >= s.min_cvss))
            ):
                picked[e.dedup_key] = e
                continue
            hits = _mentions(facts["text"], followed) if s.watched_tech else []
            if hits and SEVERITY_RANK[e.severity] >= floor and e.severity != Severity.UNKNOWN:
                picked[e.dedup_key] = Event(
                    "watched_tech",
                    e.kind,
                    e.severity,
                    f"{e.title} — affects {', '.join(hits[:3])}",
                    e.body,
                    e.link,
                    e.article_id,
                    e.dedup_key,
                    e.facts,
                )
        if s.exploited:
            for e in events["kev"]:
                picked[e.dedup_key] = e
        if s.critical_bugs and SEVERITY_RANK[Severity.CRITICAL] >= floor:
            projects = [p.lower() for p in (s.bug_projects or repos)]
            for e in events["bug"]:
                if not projects or e.facts["project"].lower() in projects:
                    picked[e.dedup_key] = e
        if s.outages:
            threshold = IMPACT_RANK[s.outage_min_impact]
            providers = [p.lower() for p in s.outage_providers]
            for e in events["outage"]:
                rank = IMPACT_RANK.get(e.facts["impact"] or "", None)
                ok = (rank is not None and rank >= threshold) or (rank is None and threshold == 1)
                if ok and (not providers or e.facts["provider"].lower() in providers):
                    picked[e.dedup_key] = e
        if s.model_releases:
            wanted = [p.lower() for p in (s.model_providers or providers_followed or [])]
            for e in events.get("model", []):
                prov = e.facts["provider"].lower()
                if not wanted or any(w in prov or prov in w for w in wanted):
                    picked[e.dedup_key] = e
        return list(picked.values())

    async def run(self) -> AlertStats:
        stats = AlertStats()
        events = await self.collect()
        if not any(events.values()):
            return stats
        rows = (
            await self.s.execute(
                select(User, UserPreference)
                .join(UserPreference, UserPreference.user_id == User.id, isouter=True)
                .where(User.is_active.is_(True))
            )
        ).all()
        for user, pref in rows:
            s = settings_for(pref)
            min_sev = pref.min_notification_severity if pref else Severity.HIGH
            followed = [
                *(pref.followed_technologies if pref else []),
                *(pref.followed_providers if pref else []),
            ]
            repos = list(pref.followed_repositories) if pref else []
            providers = list(pref.followed_providers) if pref else []
            for e in self.for_user(events, s, min_sev, followed, repos, providers):
                stats.candidates += 1
                if await deliver(self.s, user.id, e, self.now):
                    stats.created += 1
                    stats.by_rule[e.rule] = stats.by_rule.get(e.rule, 0) + 1
        log.info(
            "alerts_evaluated", created=stats.created, candidates=stats.candidates, by_rule=stats.by_rule
        )
        return stats
