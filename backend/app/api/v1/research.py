from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import ResearchFilters, ResearchPaperOut
from app.services.intel import IntelService

router = APIRouter(prefix="/research", tags=["research"], responses={400: {"model": ErrorResponse}})


@router.get("", response_model=Page[ResearchPaperOut])
async def list_papers(session: SessionDep, f: Annotated[ResearchFilters, Query()]) -> Page[ResearchPaperOut]:
    return await IntelService(session).list_papers(f)


@router.get("/{paper_id}", response_model=ResearchPaperOut, responses={404: {"model": ErrorResponse}})
async def get_paper(
    session: SessionDep,
    paper_id: Annotated[str, Path(max_length=64, description="AI Pulse UUID or arXiv id (e.g. 2501.01234)")],
) -> ResearchPaperOut:
    return await IntelService(session).get_paper(paper_id)
