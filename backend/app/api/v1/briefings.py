"""Read access to stored briefings. Generation is implemented in phase 7 (Celery)."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.ai.briefing import BriefingGenerator
from app.api.deps import AIDep, CurrentUser, OptionalUser, SessionDep
from app.core.errors import NotFoundError
from app.models import DailyBriefing
from app.schemas.common import ErrorResponse
from app.schemas.user_data import BriefingListItem, BriefingOut

router = APIRouter(prefix="/briefings", tags=["briefings"], responses={404: {"model": ErrorResponse}})


def _visible(user_id: uuid.UUID | None):  # type: ignore[no-untyped-def]
    """Global briefings (user_id NULL) plus the current user's personalised ones."""
    if user_id is None:
        return DailyBriefing.user_id.is_(None)
    return or_(DailyBriefing.user_id.is_(None), DailyBriefing.user_id == user_id)


@router.get("", response_model=list[BriefingListItem])
async def list_briefings(
    session: SessionDep, user: OptionalUser, limit: int = Query(30, ge=1, le=100)
) -> list[BriefingListItem]:
    rows = await session.scalars(
        select(DailyBriefing)
        .where(_visible(user.id if user else None))
        .order_by(DailyBriefing.briefing_date.desc(), DailyBriefing.user_id.is_(None))
        .limit(limit)
    )
    out = []
    for b in rows:
        item = BriefingListItem.model_validate(b)
        item.personalized = b.user_id is not None
        out.append(item)
    return out


@router.get("/latest", response_model=BriefingOut)
async def latest(session: SessionDep, user: OptionalUser) -> BriefingOut:
    # Prefer the user's personalised briefing over the global one for the same date.
    b = await session.scalar(
        select(DailyBriefing)
        .where(_visible(user.id if user else None))
        .order_by(DailyBriefing.briefing_date.desc(), DailyBriefing.user_id.is_(None))
        .limit(1)
    )
    if b is None:
        raise NotFoundError("No briefing has been generated yet")
    return BriefingOut.model_validate(b)


@router.post(
    "/generate",
    response_model=BriefingOut,
    summary="Generate (or refresh) today's personalised briefing now",
    description="Idempotent per user and day; one generated under 10 minutes ago is returned as is.",
)
async def generate(session: SessionDep, user: CurrentUser, ai: AIDep) -> BriefingOut:
    now = datetime.now(UTC)
    recent = await session.scalar(
        select(DailyBriefing).where(
            DailyBriefing.user_id == user.id,
            DailyBriefing.briefing_date == now.date(),
            DailyBriefing.generated_at >= now - timedelta(minutes=10),
        )
    )
    if recent is not None:
        return BriefingOut.model_validate(recent)
    b = await BriefingGenerator(session, ai, now).generate(user)
    return BriefingOut.model_validate(b)


@router.get("/{briefing_date}", response_model=BriefingOut)
async def by_date(briefing_date: date, session: SessionDep, user: OptionalUser) -> BriefingOut:
    b = await session.scalar(
        select(DailyBriefing)
        .where(_visible(user.id if user else None), DailyBriefing.briefing_date == briefing_date)
        .order_by(DailyBriefing.user_id.is_(None))
        .limit(1)
    )
    if b is None:
        raise NotFoundError("No briefing for this date")
    return BriefingOut.model_validate(b)
