"""Public reference data used by filters: categories and enabled sources."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models import Category, Source
from app.schemas.article import CategoryOut, SourceBrief

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: SessionDep) -> list[CategoryOut]:
    rows = await session.scalars(select(Category).order_by(Category.name))
    return [CategoryOut.model_validate(c) for c in rows]


@router.get("/sources", response_model=list[SourceBrief], summary="Enabled data sources")
async def list_sources(session: SessionDep) -> list[SourceBrief]:
    rows = await session.scalars(select(Source).where(Source.enabled.is_(True)).order_by(Source.name))
    return [SourceBrief.model_validate(s) for s in rows]
