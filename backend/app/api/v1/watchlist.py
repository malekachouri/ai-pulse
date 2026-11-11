"""Technology Watchlist: what is new about the user's followed technologies, providers and repositories."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.watchlist import WatchlistOut
from app.services.watchlist import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"], responses={401: {"model": ErrorResponse}})


@router.get(
    "",
    response_model=WatchlistOut,
    summary="Everything new (last 30 days) about each followed entry, linked to the original sources",
)
async def watchlist(session: SessionDep, user: CurrentUser) -> WatchlistOut:
    return await WatchlistService(session).for_user(user)
