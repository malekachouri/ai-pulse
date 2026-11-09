"""GitHub Radar. Note: GitHub has no trending API; `stars_delta_7d` is computed from our own snapshots."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import SessionDep
from app.schemas.common import ErrorResponse, Page
from app.schemas.intel import (
    GitHubIssueOut,
    GitHubRepositoryDetail,
    GitHubRepositoryOut,
    IssueFilters,
    RepoFilters,
)
from app.services.intel import IntelService

router = APIRouter(prefix="/github", tags=["github"], responses={400: {"model": ErrorResponse}})

_SEG = r"^[A-Za-z0-9_.-]{1,100}$"


@router.get("/repositories", response_model=Page[GitHubRepositoryOut])
async def list_repositories(
    session: SessionDep, f: Annotated[RepoFilters, Query()]
) -> Page[GitHubRepositoryOut]:
    return await IntelService(session).list_repos(f)


@router.get(
    "/repositories/by-name/{owner}/{name}",
    response_model=GitHubRepositoryDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_repository_by_name(
    session: SessionDep,
    owner: Annotated[str, Path(pattern=_SEG)],
    name: Annotated[str, Path(pattern=_SEG)],
) -> GitHubRepositoryDetail:
    return await IntelService(session).get_repo(full_name=f"{owner}/{name}")


@router.get(
    "/repositories/{repo_id}",
    response_model=GitHubRepositoryDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_repository(repo_id: uuid.UUID, session: SessionDep) -> GitHubRepositoryDetail:
    return await IntelService(session).get_repo(repo_id=repo_id)


@router.get("/issues", response_model=Page[GitHubIssueOut])
async def list_issues(session: SessionDep, f: Annotated[IssueFilters, Query()]) -> Page[GitHubIssueOut]:
    return await IntelService(session).list_issues(f)
