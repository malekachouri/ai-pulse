import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import AIToolOut, ToolFilters
from app.services.intel import IntelService

router = APIRouter(prefix="/tools", tags=["tools"], responses={400: {"model": ErrorResponse}})


@router.get("", response_model=Page[AIToolOut])
async def list_tools(session: SessionDep, f: Annotated[ToolFilters, Query()]) -> Page[AIToolOut]:
    return await IntelService(session).list_tools(f)


@router.get("/{tool_id}", response_model=AIToolOut, responses={404: {"model": ErrorResponse}})
async def get_tool(tool_id: uuid.UUID, session: SessionDep) -> AIToolOut:
    return await IntelService(session).get_tool(tool_id)
