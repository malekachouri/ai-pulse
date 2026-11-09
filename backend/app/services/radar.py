"""Bugs & Failures Radar: incident classification and the aggregated intelligence dashboard.

Incident categories are deterministic rules over the provider name, title and affected services (documented
in INCIDENT_RULES); the same patterns drive both API filtering (SQL `~*`) and the labels shown.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, SecurityVulnerability, SoftwareBug
from app.models.enums import BugResolution, IncidentStatus, IssueState, Severity
from app.repositories.intel import ACTIVE_INCIDENT_WINDOW, UNRESOLVED, incident_is_active, severity_rank

# category -> (providers, terms). Each term must START at a word boundary (so "rds" never matches
# "Mastercards"), but may continue ("container" matches "containers"). The same terms build the Python
# regex (\b) and the PostgreSQL regex (\y), so filtering and displayed labels always agree.
INCIDENT_RULES: dict[str, tuple[set[str], list[str]]] = {
    "ai_provider": (
        {"OpenAI", "Anthropic"},
        ["chatgpt", "gpt-", "claude", "gemini", "openai", "anthropic", "inference"],
    ),
    "cloud": (
        {"AWS", "Azure", "Google Cloud"},
        ["aws", "azure", "google cloud", "gcp", "ec2", "compute engine"],
    ),
    "api": (
        set(),
        ["api", "endpoint", "error rate", "elevated error", "5xx", "latency", "timeout", "requests"],
    ),
    "database": (
        set(),
        [
            "database",
            "postgres",
            "mysql",
            "sql",
            "rds",
            "spanner",
            "dynamodb",
            "cosmos db",
            "bigtable",
            "firestore",
            "redis",
        ],
    ),
    "kubernetes_docker": ({"Docker"}, ["kubernetes", "gke", "eks", "aks", "docker", "container"]),
    "infrastructure": (
        set(),
        [
            "network",
            "dns",
            "load balanc",
            "cdn",
            "connectivity",
            "storage",
            "region",
            "data center",
            "datacenter",
            "outage",
        ],
    ),
    "developer_platform": (
        {"GitHub"},
        ["github", "actions", "webhooks", "git operations", "packages", "codespaces", "pages"],
    ),
}


def _alternation(terms: list[str]) -> str:
    return "(?:" + "|".join(re.escape(t) for t in terms) + ")"


_PY = {k: re.compile(r"\b" + _alternation(v[1]), re.I) for k, v in INCIDENT_RULES.items()}
_PG = {
    k: r"\y" + "(" + "|".join(re.escape(t).replace("\\ ", " ") for t in v[1]) + ")"
    for k, v in INCIDENT_RULES.items()
}


def incident_categories(provider: str, title: str, services: list[str]) -> list[str]:
    text_ = f"{title} {' '.join(services)}"
    return [
        k for k, (providers, _) in INCIDENT_RULES.items() if provider in providers or _PY[k].search(text_)
    ]


def incident_category_filter(categories: list[str]) -> ColumnElement[bool]:
    conds = []
    haystack = func.concat(
        Incident.title, literal(" "), func.array_to_string(Incident.affected_services, " ")
    )
    for c in categories:
        providers, _terms = INCIDENT_RULES[c]
        parts = [haystack.op("~*")(_PG[c])]
        if providers:
            parts.append(Incident.provider.in_(providers))
        conds.append(or_(*parts))
    return or_(*conds)


def incident_state_filter(state: str, now: datetime) -> ColumnElement[bool]:
    if state == "current":
        return incident_is_active(now)
    if state == "historical":
        return Incident.status == IncidentStatus.RESOLVED
    # "unverified": unresolved per the last reading but not re-checked recently, or status unknown
    return or_(
        Incident.status == IncidentStatus.UNKNOWN,
        and_(Incident.status.in_(UNRESOLVED), Incident.last_verified_at < now - ACTIVE_INCIDENT_WINDOW),
    )


def incident_state(i: Incident, now: datetime) -> str:
    if i.status == IncidentStatus.RESOLVED:
        return "historical"
    if i.status in UNRESOLVED and i.last_verified_at >= now - ACTIVE_INCIDENT_WINDOW:
        return "current"
    return "unverified"


def duration_minutes(i: Incident) -> int | None:
    if i.started_at and i.resolved_at and i.resolved_at >= i.started_at:
        return int((i.resolved_at - i.started_at).total_seconds() // 60)
    return None


class RadarService:
    def __init__(self, session: AsyncSession, now: datetime | None = None) -> None:
        self.s = session
        self.now = now or datetime.now(UTC)

    async def summary(self, days: int = 30) -> dict[str, Any]:
        now = self.now
        since = now - timedelta(days=days)
        week_ago = now - timedelta(days=7)
        Vul, Bug, Inc = SecurityVulnerability, SoftwareBug, Incident

        critical_bugs = (
            (
                await self.s.scalars(
                    select(Bug)
                    .where(
                        Bug.status == IssueState.OPEN,
                        Bug.severity.in_([Severity.CRITICAL, Severity.HIGH]),
                        Bug.severity_basis.is_not(None),
                    )
                    .order_by(severity_rank(Bug.severity).desc(), Bug.created_at.desc())
                    .limit(10)
                )
            )
            .unique()
            .all()
        )

        new_vulns = (
            await self.s.scalars(
                select(Vul)
                .where(
                    Vul.published_at >= week_ago,
                    or_(Vul.severity.in_([Severity.CRITICAL, Severity.HIGH]), Vul.known_exploited.is_(True)),
                )
                .order_by(
                    Vul.known_exploited.desc(), Vul.cvss_score.desc().nulls_last(), Vul.published_at.desc()
                )
                .limit(10)
            )
        ).all()
        kev_recent = (
            await self.s.scalars(
                select(Vul)
                .where(Vul.kev_date_added >= week_ago.date())
                .order_by(Vul.kev_date_added.desc())
                .limit(10)
            )
        ).all()

        active = (
            await self.s.scalars(select(Inc).where(incident_is_active(now)).order_by(Inc.started_at.desc()))
        ).all()
        resolved = (
            await self.s.scalars(
                select(Inc)
                .where(
                    Inc.status == IncidentStatus.RESOLVED,
                    func.coalesce(Inc.resolved_at, Inc.started_at) >= now - timedelta(days=14),
                )
                .order_by(func.coalesce(Inc.resolved_at, Inc.started_at).desc())
                .limit(10)
            )
        ).all()
        unverified = int(
            await self.s.scalar(select(func.count(Inc.id)).where(incident_state_filter("unverified", now)))
            or 0
        )

        sev_rows = (
            (
                await self.s.execute(
                    select(Vul.severity, func.count()).where(Vul.published_at >= since).group_by(Vul.severity)
                )
            )
            .tuples()
            .all()
        )

        day = func.date_trunc("day", Inc.started_at)
        hist_rows = (
            (
                await self.s.execute(
                    select(day, Inc.provider, func.count())
                    .where(Inc.started_at >= since)
                    .group_by(day, Inc.provider)
                )
            )
            .tuples()
            .all()
        )
        history: dict[date, dict[str, int]] = {}
        for d, provider, n in hist_rows:
            history.setdefault(d.date(), {})[provider] = n
        incident_history = [
            {
                "day": (since + timedelta(days=i)).date().isoformat(),
                "by_provider": history.get((since + timedelta(days=i)).date(), {}),
                "total": sum(history.get((since + timedelta(days=i)).date(), {}).values()),
            }
            for i in range(days + 1)
        ]

        return {
            "generated_at": now,
            "window_days": days,
            "critical_bugs": critical_bugs,
            "new_vulnerabilities": new_vulns,
            "newly_exploited": kev_recent,
            "active_incidents": active,
            "resolved_incidents": resolved,
            "unverified_incidents": unverified,
            "severity_chart": [{"key": str(k), "count": n} for k, n in sev_rows],
            "most_affected": await self.most_affected(since),
            "incident_history": incident_history,
            "weekly": await self.weekly(8),
        }

    async def most_affected(self, since: datetime, limit: int = 10) -> list[dict[str, Any]]:
        rows = (
            await self.s.execute(
                text("""
            WITH v AS (
              SELECT lower(coalesce(p->>'product', p->>'vendor')) AS name, count(DISTINCT sv.id) AS n
              FROM security_vulnerabilities sv, jsonb_array_elements(sv.affected_products) p
              WHERE coalesce(sv.published_at, sv.kev_date_added::timestamptz, sv.created_at) >= :since
                AND coalesce(p->>'product', p->>'vendor') IS NOT NULL
                AND lower(coalesce(p->>'product', p->>'vendor')) NOT IN ('multiple products', 'n/a', 'unknown', '*')
              GROUP BY 1),
            b AS (SELECT lower(split_part(project, '/', 2)) AS name, count(*) AS n FROM software_bugs
                  WHERE created_at >= :since GROUP BY 1),
            i AS (SELECT lower(provider) AS name, count(*) AS n FROM incidents
                  WHERE coalesce(started_at, created_at) >= :since GROUP BY 1)
            SELECT name, coalesce(max(v.n), 0) AS vulns, coalesce(max(b.n), 0) AS bugs,
                   coalesce(max(i.n), 0) AS incidents
            FROM v FULL OUTER JOIN b USING (name) FULL OUTER JOIN i USING (name)
            WHERE name <> '' GROUP BY name
            ORDER BY coalesce(max(v.n), 0) + coalesce(max(b.n), 0) + coalesce(max(i.n), 0) DESC, name
            LIMIT :limit
        """),
                {"since": since, "limit": limit},
            )
        ).all()
        return [
            {
                "name": r.name,
                "vulnerabilities": r.vulns,
                "bugs": r.bugs,
                "incidents": r.incidents,
                "total": r.vulns + r.bugs + r.incidents,
            }
            for r in rows
        ]

    async def weekly(self, weeks: int) -> list[dict[str, Any]]:
        today = self.now.date()
        start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
        out = []
        for w in range(weeks):
            lo = datetime.combine(start + timedelta(weeks=w), datetime.min.time(), tzinfo=UTC)
            hi = lo + timedelta(weeks=1)
            Vul, Bug, Inc = SecurityVulnerability, SoftwareBug, Incident
            row = (
                await self.s.execute(
                    select(
                        select(func.count(Inc.id))
                        .where(Inc.started_at >= lo, Inc.started_at < hi)
                        .scalar_subquery(),
                        select(
                            func.coalesce(
                                func.sum(func.extract("epoch", Inc.resolved_at - Inc.started_at) / 60), 0
                            )
                        )
                        .where(
                            Inc.started_at >= lo,
                            Inc.started_at < hi,
                            Inc.resolved_at.is_not(None),
                            Inc.resolved_at
                            >= Inc.started_at,  # some providers publish inconsistent timestamps
                        )
                        .scalar_subquery(),
                        select(func.count(Vul.id))
                        .where(
                            Vul.published_at >= lo,
                            Vul.published_at < hi,
                            Vul.severity.in_([Severity.CRITICAL, Severity.HIGH]),
                        )
                        .scalar_subquery(),
                        select(func.count(Vul.id))
                        .where(Vul.kev_date_added >= lo.date(), Vul.kev_date_added < hi.date())
                        .scalar_subquery(),
                        select(func.count(Bug.id))
                        .where(Bug.created_at >= lo, Bug.created_at < hi)
                        .scalar_subquery(),
                        select(func.count(Bug.id))
                        .where(
                            Bug.resolution == BugResolution.FIXED,
                            Bug.fix_merged_at >= lo,
                            Bug.fix_merged_at < hi,
                        )
                        .scalar_subquery(),
                    )
                )
            ).one()
            out.append(
                {
                    "week_start": lo.date().isoformat(),
                    "incidents": row[0],
                    "outage_minutes": int(row[1] or 0),
                    "critical_high_cves": row[2],
                    "kev_added": row[3],
                    "bugs_reported": row[4],
                    "bugs_fixed": row[5],
                }
            )
        return out
