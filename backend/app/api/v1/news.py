import uuid
from datetime import datetime

from fastapi import APIRouter, Query, status
from pydantic import ValidationError

from app.api.deps import CurrentUser, OptionalUser, SessionDep
from app.core.errors import AppError
from app.models.enums import ItemType, Severity, VerificationStatus
from app.schemas.article import ArticleDetail, ArticleFilters, ArticleOut, SortOrder
from app.schemas.common import ErrorResponse, Page, PageParams
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
