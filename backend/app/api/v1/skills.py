import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.skills import SkillDetail, SkillFacets, SkillFilters, SkillOut
from app.services.skills import SkillsService

router = APIRouter(prefix="/skills", tags=["skills"], responses={400: {"model": ErrorResponse}})


@router.get("", response_model=Page[SkillOut])
async def list_skills(session: SessionDep, f: Annotated[SkillFilters, Query()]) -> Page[SkillOut]:
    """MCP servers, Claude Code plugins and Agent Skills from official listings, newest first."""
    return await SkillsService(session).list(f)


@router.get("/facets", response_model=SkillFacets)
async def skill_facets(session: SessionDep) -> SkillFacets:
    """Counts per kind and per AI Pulse technology, and the state of each radar source."""
    return await SkillsService(session).facets()


@router.get("/{skill_id}", response_model=SkillDetail, responses={404: {"model": ErrorResponse}})
async def get_skill(skill_id: uuid.UUID, session: SessionDep) -> SkillDetail:
    return await SkillsService(session).get(skill_id)
