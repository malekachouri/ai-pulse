from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import AppError
from app.models import UserPreference
from app.schemas.common import ErrorResponse
from app.schemas.user_data import (
    FOLLOW_FIELD,
    FOLLOW_LIMIT,
    INTERESTS,
    FollowRequest,
    PreferencesOut,
    PreferencesUpdate,
)

router = APIRouter(prefix="/preferences", tags=["preferences"], responses={401: {"model": ErrorResponse}})


async def _get_or_create(session: SessionDep, user: CurrentUser, *, lock: bool = False) -> UserPreference:
    stmt = select(UserPreference).where(UserPreference.user_id == user.id)
    pref = await session.scalar(stmt.with_for_update() if lock else stmt)
    if pref is None:
        pref = UserPreference(user_id=user.id)
        session.add(pref)
        await session.flush()
        await session.refresh(pref)
    return pref


@router.get("", response_model=PreferencesOut)
async def get_preferences(session: SessionDep, user: CurrentUser) -> PreferencesOut:
    return PreferencesOut.model_validate(await _get_or_create(session, user))


@router.put("", response_model=PreferencesOut)
async def update_preferences(
    body: PreferencesUpdate, session: SessionDep, user: CurrentUser
) -> PreferencesOut:
    pref = await _get_or_create(session, user, lock=True)
    for key, value in body.model_dump(exclude_unset=True, mode="json").items():
        if value is not None:
            setattr(pref, key, value)
    await session.flush()
    await session.refresh(pref)
    return PreferencesOut.model_validate(pref)


@router.post(
    "/follow",
    response_model=PreferencesOut,
    summary="Follow a technology, GitHub repository (owner/name) or AI provider",
    description="Idempotent and case-insensitive: following something already followed changes nothing.",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def follow(body: FollowRequest, session: SessionDep, user: CurrentUser) -> PreferencesOut:
    pref = await _get_or_create(session, user, lock=True)  # row lock: concurrent clicks never lose an entry
    field = FOLLOW_FIELD[body.type]
    current: list[str] = list(getattr(pref, field) or [])
    if body.value.lower() not in (c.lower() for c in current):
        if len(current) >= FOLLOW_LIMIT[body.type]:
            raise AppError(f"You can follow at most {FOLLOW_LIMIT[body.type]} {body.type} entries")
        setattr(pref, field, [*current, body.value])
        await session.flush()
        await session.refresh(pref)
    return PreferencesOut.model_validate(pref)


@router.post("/unfollow", response_model=PreferencesOut, summary="Stop following an entry (idempotent)")
async def unfollow(body: FollowRequest, session: SessionDep, user: CurrentUser) -> PreferencesOut:
    pref = await _get_or_create(session, user, lock=True)
    field = FOLLOW_FIELD[body.type]
    current: list[str] = list(getattr(pref, field) or [])
    kept = [c for c in current if c.lower() != body.value.lower()]
    if len(kept) != len(current):
        setattr(pref, field, kept)
        await session.flush()
        await session.refresh(pref)
    return PreferencesOut.model_validate(pref)


@router.get("/options", summary="Allowed interest values")
async def options() -> dict[str, list[str]]:
    return {"interests": INTERESTS}
