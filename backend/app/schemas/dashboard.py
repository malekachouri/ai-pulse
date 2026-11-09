from datetime import date

from pydantic import BaseModel

from app.schemas.article import ArticleOut


class CountByKey(BaseModel):
    key: str
    count: int


class DailyCount(BaseModel):
    day: date
    count: int


class DashboardSummary(BaseModel):
    total_articles: int
    articles_last_24h: int
    model_releases_7d: int
    new_github_issues_7d: int
    critical_vulnerabilities_7d: int
    known_exploited_7d: int
    active_incidents: int
    sources_enabled: int
    sources_failing: int
    by_item_type: list[CountByKey]
    by_category: list[CountByKey]
    by_severity: list[CountByKey]
    trending_tags: list[CountByKey]
    activity_14d: list[DailyCount]
    latest: list[ArticleOut]
    latest_ai: list[ArticleOut]
    top_security: list[ArticleOut]
    recent_failures: list[ArticleOut]
