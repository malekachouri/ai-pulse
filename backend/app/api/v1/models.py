import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import AIModelDetail, AIModelOut, ModelFilters, ReleaseFilters, ReleaseOut
from app.services.intel import IntelService

router = APIRouter(prefix="/models", tags=["models"], responses={400: {"model": ErrorResponse}})


@router.get("", response_model=Page[AIModelOut], summary="AI models with their latest release")
async def list_models(session: SessionDep, f: Annotated[ModelFilters, Query()]) -> Page[AIModelOut]:
    return await IntelService(session).list_models(f)


@router.get("/releases", response_model=Page[ReleaseOut], summary="Model releases, newest first by default")
async def list_releases(session: SessionDep, f: Annotated[ReleaseFilters, Query()]) -> Page[ReleaseOut]:
    return await IntelService(session).list_releases(f)


@router.get("/{model_id}", response_model=AIModelDetail, responses={404: {"model": ErrorResponse}})
async def get_model(model_id: uuid.UUID, session: SessionDep) -> AIModelDetail:
    return await IntelService(session).get_model(model_id)
