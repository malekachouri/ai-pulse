from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import OptionalUser, SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.search import SearchParams, SearchResponse
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"], responses={501: {"model": ErrorResponse}})


@router.get(
    "",
    response_model=SearchResponse,
    summary="Search all collected items",
    description="Keyword search with relevance ranking and highlighted snippets. "
    "`semantic` and `hybrid` modes return 501 until embeddings are generated (AI engine phase).",
)
async def search(
    session: SessionDep, user: OptionalUser, p: Annotated[SearchParams, Query()]
) -> SearchResponse:
    return await SearchService(session).search(p, user)
