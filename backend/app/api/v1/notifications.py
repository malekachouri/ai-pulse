import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.models import Notification
from app.schemas.common import ErrorResponse, Page, PageParams
from app.schemas.user_data import NotificationOut, UnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"], responses={401: {"model": ErrorResponse}})


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    session: SessionDep,
    user: CurrentUser,
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[NotificationOut]:
    params = PageParams(page=page, page_size=page_size)
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(Notification.created_at.desc()).offset(params.offset).limit(params.page_size)
    )
    return Page.build([NotificationOut.model_validate(n) for n in rows], total, params)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(session: SessionDep, user: CurrentUser) -> UnreadCount:
    n = await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    )
    return UnreadCount(unread=n or 0)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def mark_read(notification_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> None:
    n = await session.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFoundError("Notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(session: SessionDep, user: CurrentUser) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
