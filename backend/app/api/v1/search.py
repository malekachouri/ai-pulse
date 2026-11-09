from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.ai.rag import RagService
from app.api.deps import AIDep, OptionalUser, SessionDep
from app.models import Article
from app.schemas.article import ArticleFilters
from app.schemas.common import ErrorResponse
from app.schemas.search import AskRequest, AskResponse, SearchCapabilities, SearchParams, SearchResponse
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"], responses={501: {"model": ErrorResponse}})


@router.get(
    "",
    response_model=SearchResponse,
    summary="Search all collected items",
    description=(
        "`keyword`: PostgreSQL full-text ranking with highlighted snippets. "
        "`semantic`: pgvector cosine similarity. "
        "`hybrid`: BM25 + semantic fused with Reciprocal Rank Fusion. "
        "Semantic modes return 501 when no embedding provider is configured."
    ),
)
async def search(
    session: SessionDep, user: OptionalUser, ai: AIDep, p: Annotated[SearchParams, Query()]
) -> SearchResponse:
    return await SearchService(session, ai.embedder).search(p, user)


@router.get("/capabilities", response_model=SearchCapabilities)
async def capabilities(session: SessionDep, ai: AIDep) -> SearchCapabilities:
    total = await session.scalar(select(func.count(Article.id))) or 0
    embedded = await session.scalar(select(func.count(Article.id)).where(Article.embedding.is_not(None))) or 0
    has_vec = ai.embedder is not None and embedded > 0
    return SearchCapabilities(
        semantic=has_vec,
        hybrid=has_vec,
        ask=True,
        ask_mode="generative" if ai.llm else "sources-only",
        embedded_items=embedded,
        total_items=total,
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question; answered only from collected items, with citations",
    description=(
        "Returns `insufficient=true` (and no answer) when collected information cannot support an answer. "
        "Without an LLM provider the most relevant sources are returned without a generated answer."
    ),
)
async def ask(body: AskRequest, session: SessionDep, user: OptionalUser, ai: AIDep) -> AskResponse:
    filters = ArticleFilters(item_type=body.item_type, category=body.category, date_from=body.date_from)
    result = await RagService(session, ai).ask(body.question, filters, user, body.max_sources)
    return AskResponse(**asdict(result))
