from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import (
    SecurityStats,
    VulnerabilityDetail,
    VulnerabilityFilters,
    VulnerabilityOut,
    validate_cve,
)
from app.services.intel import IntelService

router = APIRouter(prefix="/security", tags=["security"], responses={400: {"model": ErrorResponse}})


@router.get("/vulnerabilities", response_model=Page[VulnerabilityOut])
async def list_vulnerabilities(
    session: SessionDep, f: Annotated[VulnerabilityFilters, Query()]
) -> Page[VulnerabilityOut]:
    return await IntelService(session).list_vulns(f)


@router.get("/stats", response_model=SecurityStats)
async def stats(session: SessionDep) -> SecurityStats:
    return await IntelService(session).vuln_stats()


@router.get(
    "/vulnerabilities/{cve_id}", response_model=VulnerabilityDetail, responses={404: {"model": ErrorResponse}}
)
async def get_vulnerability(
    session: SessionDep, cve_id: Annotated[str, Path(max_length=32)]
) -> VulnerabilityDetail:
    try:
        cve = validate_cve(cve_id)
    except ValueError as exc:
        raise AppError(str(exc)) from exc
    return await IntelService(session).get_vuln(cve)
