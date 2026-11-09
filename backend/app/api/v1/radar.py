"""Bugs & Failures Radar dashboard."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.intel import RadarSummary, VulnerabilityOut
from app.services.intel import IntelService, bug_out
from app.services.radar import RadarService

router = APIRouter(prefix="/radar", tags=["radar"])


@router.get(
    "/summary",
    response_model=RadarSummary,
    summary="Critical bugs, new/exploited CVEs, current vs resolved incidents, trends",
    description=(
        "Critical bugs require a documented severity basis. Incidents are 'current' only when the "
        "provider's status data says unresolved and AI Pulse verified it within 2 hours; older "
        "unresolved ones are counted as 'unverified', never as active."
    ),
)
async def radar_summary(session: SessionDep, days: int = Query(30, ge=7, le=90)) -> RadarSummary:
    now = datetime.now(UTC)
    data = await RadarService(session, now).summary(days)
    intel = IntelService(session)
    return RadarSummary(
        **{
            k: data[k]
            for k in (
                "generated_at",
                "window_days",
                "unverified_incidents",
                "severity_chart",
                "most_affected",
                "incident_history",
                "weekly",
            )
        },
        critical_bugs=[bug_out(b) for b in data["critical_bugs"]],
        new_vulnerabilities=[VulnerabilityOut.model_validate(v) for v in data["new_vulnerabilities"]],
        newly_exploited=[VulnerabilityOut.model_validate(v) for v in data["newly_exploited"]],
        active_incidents=[intel._incident(i, now) for i in data["active_incidents"]],
        resolved_incidents=[intel._incident(i, now) for i in data["resolved_incidents"]],
    )
