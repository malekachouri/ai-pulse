from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import UserPreference
from app.schemas.common import ErrorResponse
from app.schemas.user_data import INTERESTS, PreferencesOut, PreferencesUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"], responses={401: {"model": ErrorResponse}})


async def _get_or_create(session: SessionDep, user: CurrentUser) -> UserPreference:
    pref = await session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
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
    pref = await _get_or_create(session, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(pref, key, value)
    await session.flush()
    await session.refresh(pref)
    return PreferencesOut.model_validate(pref)


@router.get("/options", summary="Allowed interest values")
async def options() -> dict[str, list[str]]:
    return {"interests": INTERESTS}
