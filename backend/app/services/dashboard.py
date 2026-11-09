from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Article,
    Category,
    Incident,
    SecurityVulnerability,
    Source,
    User,
    article_categories,
)
from app.models.enums import IncidentStatus, ItemType, Severity
from app.repositories.articles import ArticleRepository
from app.schemas.article import ArticleFilters, SortOrder
from app.schemas.dashboard import CountByKey, DailyCount, DashboardSummary
from app.services.articles import ArticleService


class DashboardService:
    """All figures are computed from collected data - nothing is estimated or invented."""

    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def _count(self, stmt) -> int:  # type: ignore[no-untyped-def]
        return int(await self.s.scalar(stmt) or 0)

    async def summary(self, user: User | None = None) -> DashboardSummary:
        now = datetime.now(UTC)
        d1, d7, d14 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=14)
        when = func.coalesce(Article.published_at, Article.collected_at)
        non_dup = Article.duplicate_of_id.is_(None)

        total = await self._count(select(func.count(Article.id)).where(non_dup))
        last24 = await self._count(select(func.count(Article.id)).where(non_dup, Article.collected_at >= d1))

        # Counts come from the canonical articles table so they always agree with the lists shown.
        def typed(t: ItemType, since: datetime):  # type: ignore[no-untyped-def]
            return select(func.count(Article.id)).where(non_dup, Article.item_type == t, when >= since)

        releases = await self._count(typed(ItemType.MODEL_RELEASE, d7))
        issues = await self._count(typed(ItemType.GITHUB_ISSUE, d7))
        critical = await self._count(
            typed(ItemType.VULNERABILITY, d7).where(Article.severity == Severity.CRITICAL)
        )
        vuln_when = func.coalesce(SecurityVulnerability.published_at, SecurityVulnerability.created_at)
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
        by_sev = [
            CountByKey(key=str(sev), count=c)
            for sev, c in (
                await self.s.execute(
                    select(Article.severity, func.count())
                    .where(non_dup, Article.severity.is_not(None), when >= d14)
                    .group_by(Article.severity)
                )
            ).all()
        ]
        tag = func.unnest(Article.tags).label("tag")
        tag_rows = select(tag).where(non_dup, when >= d7).subquery()
        trending = [
            CountByKey(key=t, count=c)
            for t, c in (
                await self.s.execute(
                    select(tag_rows.c.tag, func.count())
                    .group_by(tag_rows.c.tag)
                    .order_by(func.count().desc(), tag_rows.c.tag)
                    .limit(12)
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
        latest_ai, _ = await repo.search(
            ArticleFilters(item_type=[ItemType.NEWS, ItemType.MODEL_RELEASE, ItemType.TOOL]), 0, 5
        )
        failures, _ = await repo.search(
            ArticleFilters(item_type=[ItemType.BUG, ItemType.INCIDENT], date_from=d14), 0, 5
        )
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
        svc = ArticleService(self.s)
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
            by_severity=by_sev,
            trending_tags=trending,
            activity_14d=activity,
            latest=await svc.to_out(latest, user),
            latest_ai=await svc.to_out(latest_ai, user),
            top_security=await svc.to_out(security, user),
            recent_failures=await svc.to_out(failures, user),
        )
