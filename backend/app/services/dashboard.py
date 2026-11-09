from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIModelRelease,
    Article,
    Category,
    GitHubIssue,
    Incident,
    SecurityVulnerability,
    Source,
    article_categories,
)
from app.models.enums import IncidentStatus, ItemType, Severity
from app.repositories.articles import ArticleRepository
from app.schemas.article import ArticleFilters, ArticleOut, SortOrder
from app.schemas.dashboard import CountByKey, DailyCount, DashboardSummary


class DashboardService:
    """All figures are computed from collected data - nothing is estimated or invented."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def _count(self, stmt) -> int:  # type: ignore[no-untyped-def]
        return int(await self.s.scalar(stmt) or 0)

    async def summary(self) -> DashboardSummary:
        now = datetime.now(UTC)
        d1, d7, d14 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=14)
        when = func.coalesce(Article.published_at, Article.collected_at)
        non_dup = Article.duplicate_of_id.is_(None)

        total = await self._count(select(func.count(Article.id)).where(non_dup))
        last24 = await self._count(select(func.count(Article.id)).where(non_dup, Article.collected_at >= d1))
        releases = await self._count(
            select(func.count(AIModelRelease.id)).where(
                func.coalesce(AIModelRelease.released_at, AIModelRelease.created_at) >= d7
            )
        )
        issues = await self._count(select(func.count(GitHubIssue.id)).where(GitHubIssue.opened_at >= d7))
        vuln_when = func.coalesce(SecurityVulnerability.published_at, SecurityVulnerability.created_at)
        critical = await self._count(
            select(func.count(SecurityVulnerability.id)).where(
                SecurityVulnerability.severity == Severity.CRITICAL, vuln_when >= d7
            )
        )
        kev = await self._count(
            select(func.count(SecurityVulnerability.id)).where(
                SecurityVulnerability.known_exploited.is_(True),
                func.coalesce(cast(SecurityVulnerability.kev_date_added, Date), cast(vuln_when, Date))
                >= d7.date(),
            )
        )
        # Active = not resolved per the provider's own status data, verified within the last 2 hours.
        active = await self._count(
            select(func.count(Incident.id)).where(
                Incident.status != IncidentStatus.RESOLVED,
                Incident.status != IncidentStatus.UNKNOWN,
                Incident.last_verified_at >= now - timedelta(hours=2),
            )
        )
        enabled = await self._count(select(func.count(Source.id)).where(Source.enabled.is_(True)))
        failing = await self._count(
            select(func.count(Source.id)).where(Source.enabled.is_(True), Source.consecutive_failures >= 3)
        )

        by_type = [
            CountByKey(key=str(t), count=c)
            for t, c in (
                await self.s.execute(
                    select(Article.item_type, func.count()).where(non_dup).group_by(Article.item_type)
                )
            ).all()
        ]
        by_cat = [
            CountByKey(key=slug, count=c)
            for slug, c in (
                await self.s.execute(
                    select(Category.slug, func.count())
                    .join(article_categories, article_categories.c.category_id == Category.id)
                    .group_by(Category.slug)
                    .order_by(func.count().desc())
                )
            ).all()
        ]
        day = cast(when, Date)
        activity_rows = dict(
            (await self.s.execute(select(day, func.count()).where(non_dup, when >= d14).group_by(day))).all()
        )
        activity = [
            DailyCount(
                day=(now - timedelta(days=i)).date(),
                count=activity_rows.get((now - timedelta(days=i)).date(), 0),
            )
            for i in range(13, -1, -1)
        ]

        repo = ArticleRepository(self.s)
        latest, _ = await repo.search(ArticleFilters(sort=SortOrder.LATEST), 0, 8)
        security, _ = await repo.search(
            ArticleFilters(
                item_type=[ItemType.VULNERABILITY],
                severity=[Severity.CRITICAL, Severity.HIGH],
                date_from=d14,
                sort=SortOrder.LATEST,
            ),
            0,
            5,
        )
        return DashboardSummary(
            total_articles=total,
            articles_last_24h=last24,
            model_releases_7d=releases,
            new_github_issues_7d=issues,
            critical_vulnerabilities_7d=critical,
            known_exploited_7d=kev,
            active_incidents=active,
            sources_enabled=enabled,
            sources_failing=failing,
            by_item_type=by_type,
            by_category=by_cat,
            activity_14d=activity,
            latest=[ArticleOut.model_validate(a) for a in latest],
            top_security=[ArticleOut.model_validate(a) for a in security],
        )
