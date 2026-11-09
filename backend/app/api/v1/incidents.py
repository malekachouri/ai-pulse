import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import IncidentDetail, IncidentFilters, IncidentOut
from app.services.intel import IntelService

router = APIRouter(prefix="/incidents", tags=["incidents"], responses={400: {"model": ErrorResponse}})


@router.get(
    "",
    response_model=Page[IncidentOut],
    summary="Provider incidents",
    description=(
        "`is_active` is true only when the provider's own status page reports the incident as unresolved "
        "and AI Pulse verified that within the last 2 hours. Unresolved but unverified incidents are "
        "flagged `status_is_stale`."
    ),
)
async def list_incidents(session: SessionDep, f: Annotated[IncidentFilters, Query()]) -> Page[IncidentOut]:
    return await IntelService(session).list_incidents(f)


@router.get("/{incident_id}", response_model=IncidentDetail, responses={404: {"model": ErrorResponse}})
async def get_incident(incident_id: uuid.UUID, session: SessionDep) -> IncidentDetail:
    return await IntelService(session).get_incident(incident_id)
