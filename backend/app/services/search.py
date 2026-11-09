"""Keyword search over collected items (PostgreSQL FTS). Semantic/hybrid modes arrive with embeddings."""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Article, User
from app.repositories.articles import ArticleRepository
from app.schemas.article import ArticleFilters, SortOrder
from app.schemas.search import (
    HIGHLIGHT_END,
    HIGHLIGHT_START,
    SearchHit,
    SearchMode,
    SearchParams,
    SearchResponse,
)
from app.services.articles import ArticleService


class SemanticSearchUnavailable(AppError):
    status_code = 501
    code = "not_available"


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def search(self, p: SearchParams, user: User | None) -> SearchResponse:
        if p.mode != SearchMode.KEYWORD:
            raise SemanticSearchUnavailable(
                f"'{p.mode}' search needs embeddings, which are not generated yet. Use mode=keyword."
            )
        filters = ArticleFilters(
            q=p.q, item_type=p.item_type, category=p.category, severity=p.severity,
            date_from=p.date_from, date_to=p.date_to, sort=SortOrder.RELEVANCE,
        )  # fmt: skip
        stmt, ts_query = ArticleRepository(self.s).filtered(filters)
        assert ts_query is not None
        total = await self.s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rank = func.ts_rank_cd(Article.search_vector, ts_query)
        doc = func.concat_ws(" ", Article.title, Article.description, func.left(Article.content, 5000))
        snippet = func.ts_headline(
            "english",
            doc,
            ts_query,
            f"StartSel={HIGHLIGHT_START}, StopSel={HIGHLIGHT_END}, MaxWords=35, MinWords=15, MaxFragments=2",
        )
        rows = (
            await self.s.execute(
                stmt.add_columns(rank.label("rank"), snippet.label("snippet"))
                .order_by(desc("rank"), desc(func.coalesce(Article.published_at, Article.collected_at)))
                .offset(p.paging.offset)
                .limit(p.page_size)
            )
        ).all()
        articles = await ArticleService(self.s).to_out([r[0] for r in rows], user)
        hits = [
            SearchHit(article=a, rank=round(float(r.rank), 6), snippet=r.snippet)
            for a, r in zip(articles, rows, strict=True)
        ]
        pages = (total + p.page_size - 1) // p.page_size if total else 0
        return SearchResponse(
            query=p.q, mode=p.mode, items=hits, total=total, page=p.page, page_size=p.page_size, pages=pages
        )
