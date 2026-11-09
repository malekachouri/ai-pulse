from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Overview KPIs computed from collected data")
async def summary(session: SessionDep) -> DashboardSummary:
    return await DashboardService(session).summary()
