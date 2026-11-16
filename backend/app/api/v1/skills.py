import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import AIDep, CurrentUser, SessionDep, SettingsDep
from app.core.errors import AppError, NotFoundError
from app.core.ratelimit import limiter
from app.ingestion.http import HttpClient
from app.models import AISkill
from app.schemas.common import ErrorResponse, Page
from app.schemas.skills import SkillDetail, SkillExplanationOut, SkillFacets, SkillFilters, SkillOut
from app.services.skills import SkillsService
from app.skills.explain import SkillExplainer

router = APIRouter(prefix="/skills", tags=["skills"], responses={400: {"model": ErrorResponse}})


@router.get("", response_model=Page[SkillOut])
async def list_skills(session: SessionDep, f: Annotated[SkillFilters, Query()]) -> Page[SkillOut]:
    """MCP servers, Claude Code plugins and Agent Skills from official listings, newest first."""
    return await SkillsService(session).list(f)


@router.get("/facets", response_model=SkillFacets)
async def skill_facets(session: SessionDep, ai: AIDep) -> SkillFacets:
    """Counts per kind and per AI Pulse technology, and the state of each radar source."""
    out = await SkillsService(session).facets()
    out.llm_available = ai.llm is not None
    return out


@router.get("/{skill_id}", response_model=SkillDetail, responses={404: {"model": ErrorResponse}})
async def get_skill(skill_id: uuid.UUID, session: SessionDep) -> SkillDetail:
    return await SkillsService(session).get(skill_id)


async def _skill(session: SessionDep, skill_id: uuid.UUID) -> AISkill:
    skill = await session.get(AISkill, skill_id)
    if skill is None:
        raise NotFoundError("Skill not found")
    return skill


@router.get(
    "/{skill_id}/explanation",
    response_model=SkillExplanationOut,
    summary="The stored AI explanation of what the entry is good for, if one was generated",
    responses={404: {"model": ErrorResponse}},
)
async def get_explanation(skill_id: uuid.UUID, session: SessionDep, ai: AIDep) -> SkillExplanationOut:
    skill = await _skill(session, skill_id)
    stored = skill.explanation or {"status": "none"}
    return SkillExplanationOut.model_validate({**stored, "llm_available": ai.llm is not None})


@router.post(
    "/{skill_id}/explanation",
    response_model=SkillExplanationOut,
    dependencies=[limiter("ai", per_user=True)],
    summary="Generate the AI explanation (grounded in the listing and README; cited)",
    responses={404: {"model": ErrorResponse}},
)
async def generate_explanation(
    skill_id: uuid.UUID, request: Request, session: SessionDep, user: CurrentUser, ai: AIDep,
    settings: SettingsDep,
) -> SkillExplanationOut:  # fmt: skip
    skill = await _skill(session, skill_id)
    if ai.llm is None:
        raise AppError("Explanations need an LLM provider (LLM_PROVIDER / LLM_MODEL).")
    http = getattr(request.app.state, "skill_http", None)
    own = http is None
    if own:
        http = HttpClient(block_private=not settings.ingestion_allow_private_hosts)
    try:
        out = await SkillExplainer(session, ai, http).generate(skill)
    finally:
        if own:
            await http.aclose()
    return SkillExplanationOut.model_validate({**out, "llm_available": True})
