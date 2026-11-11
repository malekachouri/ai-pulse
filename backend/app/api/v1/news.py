import uuid
from datetime import datetime

from fastapi import APIRouter, Query, status
from pydantic import ValidationError

from app.ai.bugintel import BugIntelligence
from app.api.deps import AIDep, CurrentUser, OptionalUser, SessionDep
from app.core.errors import AppError, NotFoundError
from app.core.ratelimit import limiter
from app.models import Article
from app.models.enums import ItemType, Severity, VerificationStatus
from app.schemas.ai import ArticleAnalysisOut
from app.schemas.article import ArticleDetail, ArticleFilters, ArticleOut, SortOrder
from app.schemas.bugintel import BugIntelligenceOut
from app.schemas.common import ErrorResponse, Page, PageParams
from app.services.ai import AIService
from app.services.articles import ArticleService

router = APIRouter(prefix="/news", tags=["news"])


def build_filters(
    q: str | None = Query(None, max_length=300),
    item_type: list[ItemType] | None = Query(None),
    category: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    severity: list[Severity] | None = Query(None),
    min_importance: float | None = Query(None, ge=0, le=100),
    verification: list[VerificationStatus] | None = Query(None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_duplicates: bool = False,
    sort: SortOrder = SortOrder.LATEST,
) -> ArticleFilters:
    try:
        return ArticleFilters(
            q=q,
            item_type=item_type,
            category=category,
            source=source,
            severity=severity,
            min_importance=min_importance,
            verification=verification,
            date_from=date_from,
            date_to=date_to,
            include_duplicates=include_duplicates,
            sort=sort,
        )
    except ValidationError as exc:
        msg = exc.errors()[0]["msg"].removeprefix("Value error, ")
        raise AppError(msg) from exc


@router.get("", response_model=Page[ArticleOut], summary="Search and filter collected items")
async def list_news(
    session: SessionDep,
    user: OptionalUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=300),
    item_type: list[ItemType] | None = Query(None),
    category: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    severity: list[Severity] | None = Query(None),
    min_importance: float | None = Query(None, ge=0, le=100),
    verification: list[VerificationStatus] | None = Query(None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_duplicates: bool = False,
    sort: SortOrder = SortOrder.LATEST,
) -> Page[ArticleOut]:
    f = build_filters(
        q,
        item_type,
        category,
        source,
        severity,
        min_importance,
        verification,
        date_from,
        date_to,
        include_duplicates,
        sort,
    )
    return await ArticleService(session).search(f, PageParams(page=page, page_size=page_size), user)


@router.get("/{article_id}", response_model=ArticleDetail, responses={404: {"model": ErrorResponse}})
async def get_news(article_id: uuid.UUID, session: SessionDep, user: OptionalUser) -> ArticleDetail:
    return await ArticleService(session).get(article_id, user)


@router.put("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(article_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await ArticleService(session).set_read(article_id, user, True)


@router.delete("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_unread(article_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    await ArticleService(session).set_read(article_id, user, False)


@router.get(
    "/{article_id}/analysis",
    response_model=ArticleAnalysisOut,
    summary="AI analysis (labelled AI-generated) and the explainable importance breakdown",
    responses={404: {"model": ErrorResponse}},
)
async def get_analysis(
    article_id: uuid.UUID, session: SessionDep, user: OptionalUser, ai: AIDep
) -> ArticleAnalysisOut:
    return await AIService(session, ai).analysis(article_id, user)


async def _bug_article(session: SessionDep, article_id: uuid.UUID) -> Article:
    a = await session.get(Article, article_id)
    if a is None:
        raise NotFoundError("Article not found")
    return a


@router.get(
    "/{article_id}/bug-intelligence",
    response_model=BugIntelligenceOut,
    summary="Why a bug/CVE occurs, impact, affected versions and fixes, from cited official sources",
    description="Returns the stored AI explanation when one was generated, otherwise the cited facts only.",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def get_bug_intelligence(article_id: uuid.UUID, session: SessionDep, ai: AIDep) -> BugIntelligenceOut:
    a = await _bug_article(session, article_id)
    intel = BugIntelligence(session, ai)
    try:
        out = await intel.cached(a) or await intel.build(a, use_llm=False)
    except ValueError as exc:
        raise AppError(str(exc)) from exc
    return BugIntelligenceOut.model_validate({**out, "llm_available": ai.llm is not None})


@router.post(
    "/{article_id}/bug-intelligence",
    response_model=BugIntelligenceOut,
    dependencies=[limiter("ai", per_user=True)],
    summary="Generate the AI explanation (grounded, cited); needs an LLM provider",
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def generate_bug_intelligence(
    article_id: uuid.UUID, session: SessionDep, user: CurrentUser, ai: AIDep
) -> BugIntelligenceOut:
    a = await _bug_article(session, article_id)
    if ai.llm is None:
        raise AppError("Bug intelligence explanations need an LLM provider (LLM_PROVIDER / LLM_MODEL).")
    try:
        out = await BugIntelligence(session, ai).generate(a)
    except ValueError as exc:
        raise AppError(str(exc)) from exc
    return BugIntelligenceOut.model_validate({**out, "llm_available": True})
