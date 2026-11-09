"""Keyword search over collected items (PostgreSQL FTS). Semantic/hybrid modes arrive with embeddings."""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import Embedder, ProviderError
from app.ai.search import Retriever
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
    def __init__(self, session: AsyncSession, embedder: Embedder | None = None) -> None:
        self.s = session
        self.embedder = embedder

    async def _vector_search(self, p: SearchParams, user: User | None) -> SearchResponse:
        filters = ArticleFilters(
            item_type=p.item_type,
            category=p.category,
            severity=p.severity,
            date_from=p.date_from,
            date_to=p.date_to,
        )
        retriever = Retriever(self.s, self.embedder)
        try:
            if p.mode == SearchMode.SEMANTIC:
                hits = await retriever.semantic(p.q, filters)
            else:
                hits = await retriever.hybrid(p.q, filters, natural=False)
        except ProviderError as exc:
            raise SemanticSearchUnavailable(f"The embedding provider failed: {exc}") from exc
        page = hits[p.paging.offset : p.paging.offset + p.page_size]
        articles = await ArticleService(self.s).to_out([h.article for h in page], user)
        items = [
            SearchHit(
                article=a,
                rank=round(h.score, 6),
                snippet=a.description[:300] if a.description else None,
                scores=h.scores,
            )
            for a, h in zip(articles, page, strict=True)
        ]
        total = len(hits)
        pages = (total + p.page_size - 1) // p.page_size if total else 0
        return SearchResponse(
            query=p.q, mode=p.mode, items=items, total=total, page=p.page, page_size=p.page_size, pages=pages
        )

    async def search(self, p: SearchParams, user: User | None) -> SearchResponse:
        if p.mode != SearchMode.KEYWORD:
            if self.embedder is None:
                raise SemanticSearchUnavailable(
                    f"'{p.mode}' search needs an embedding provider "
                    "(set EMBEDDING_PROVIDER/EMBEDDING_MODEL). Use mode=keyword."
                )
            return await self._vector_search(p, user)
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
