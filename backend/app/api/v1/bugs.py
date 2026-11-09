import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import BugFilters, SoftwareBugOut
from app.services.intel import IntelService

router = APIRouter(prefix="/bugs", tags=["bugs"], responses={400: {"model": ErrorResponse}})


@router.get(
    "", response_model=Page[SoftwareBugOut], summary="Public bug reports; severity always has a basis"
)
async def list_bugs(session: SessionDep, f: Annotated[BugFilters, Query()]) -> Page[SoftwareBugOut]:
    return await IntelService(session).list_bugs(f)


@router.get("/{bug_id}", response_model=SoftwareBugOut, responses={404: {"model": ErrorResponse}})
async def get_bug(bug_id: uuid.UUID, session: SessionDep) -> SoftwareBugOut:
    return await IntelService(session).get_bug(bug_id)
