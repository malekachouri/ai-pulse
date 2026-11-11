"""Learning: personalised recommendations (rule-based, explained) and daily AI lessons (labelled)."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.ai.briefing import local_now
from app.ai.lessons import LessonGenerator, LessonsDisabledError
from app.api.deps import AIDep, CurrentUser, SessionDep
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.models import LearningLesson, UserPreference
from app.schemas.common import ErrorResponse
from app.schemas.recommendations import LessonOut, LessonsOut, RecommendationsOut
from app.services.recommendations import RecommendationService

router = APIRouter(prefix="/learning", tags=["learning"], responses={401: {"model": ErrorResponse}})


@router.get(
    "/recommendations",
    response_model=RecommendationsOut,
    summary="What to learn next, with the reason for each item",
)
async def recommendations(
    session: SessionDep, user: CurrentUser, limit: int = Query(12, ge=1, le=30)
) -> RecommendationsOut:
    return await RecommendationService(session).for_user(user, limit)


def _out(row: LearningLesson) -> LessonOut:
    c = row.content
    return LessonOut(
        id=str(row.id),
        position=row.position,
        title=c["title"],
        explanation=c["explanation"],
        key_points=c.get("key_points", []),
        why_it_matters=c.get("why_it_matters", ""),
        try_it=c.get("try_it"),
        topics=c.get("topics", []),
        resources=c.get("resources", []),
        source=c["source"],
        personal_reason=c.get("personal_reason"),
        unsupported_claims_removed=c.get("unsupported_claims_removed", []),
        provider=row.provider,
        model=row.model,
        created_at=row.created_at.isoformat(),
    )


async def _today(session: SessionDep, user: CurrentUser) -> date:
    pref = await session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    return local_now(pref, datetime.now(UTC)).date()


@router.get("/lessons", response_model=LessonsOut, summary="Lessons of a day (default: today, local time)")
async def lessons(
    session: SessionDep, user: CurrentUser, ai: AIDep, lesson_date: date | None = Query(None)
) -> LessonsOut:
    day = lesson_date or await _today(session, user)
    rows = (
        await session.scalars(
            select(LearningLesson)
            .where(LearningLesson.user_id == user.id, LearningLesson.lesson_date == day)
            .order_by(LearningLesson.position)
        )
    ).all()
    status = "ready" if rows else ("empty" if ai.llm else "disabled")
    return LessonsOut(lesson_date=day.isoformat(), status=status, lessons=[_out(r) for r in rows])


@router.post(
    "/lessons/generate",
    dependencies=[limiter("ai", per_user=True)],
    response_model=LessonsOut,
    summary="Generate today's lessons now",
    description="Uses the configured LLM. Lessons generated under 10 minutes ago are returned as they are.",
    responses={400: {"model": ErrorResponse}},
)
async def generate(session: SessionDep, user: CurrentUser, ai: AIDep) -> LessonsOut:
    day = await _today(session, user)
    now = datetime.now(UTC)
    recent = (
        await session.scalars(
            select(LearningLesson)
            .where(
                LearningLesson.user_id == user.id,
                LearningLesson.lesson_date == day,
                LearningLesson.created_at >= now - timedelta(minutes=10),
            )
            .order_by(LearningLesson.position)
        )
    ).all()
    if not recent:
        try:
            recent = await LessonGenerator(session, ai, now).generate(user, day)
        except LessonsDisabledError as exc:
            raise AppError(str(exc)) from exc
    return LessonsOut(
        lesson_date=day.isoformat(), status="ready" if recent else "empty", lessons=[_out(r) for r in recent]
    )
