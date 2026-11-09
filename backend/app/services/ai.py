import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import RULES_VERSION
from app.ai.prompts import PROMPT_VERSION
from app.ai.providers import AIProviders
from app.ai.scoring import VERSION as SCORE_VERSION
from app.ai.scoring import personalize
from app.core.errors import NotFoundError
from app.models import AIAnalysis, AIUsage, Article, User, UserPreference
from app.models.enums import AnalysisKind
from app.schemas.ai import AIStatus, AnalysisStatus, ArticleAnalysisOut, ImportanceBreakdown


class AIService:
    def __init__(self, session: AsyncSession, providers: AIProviders) -> None:
        self.s = session
        self.p = providers

    async def analysis(self, article_id: uuid.UUID, user: User | None) -> ArticleAnalysisOut:
        article = await self.s.get(Article, article_id)
        if article is None:
            raise NotFoundError("Article not found")
        rows = {
            (r.kind, r.prompt_version): r
            for r in await self.s.scalars(select(AIAnalysis).where(AIAnalysis.article_id == article_id))
        }
        summary = rows.get((AnalysisKind.SUMMARY, PROMPT_VERSION))
        if summary is not None and summary.valid:
            status = AnalysisStatus(
                status="ready",
                provider=summary.provider,
                model=summary.model,
                generated_at=summary.created_at,
            )
        elif summary is not None:
            status = AnalysisStatus(
                status="failed",
                provider=summary.provider,
                model=summary.model,
                generated_at=summary.created_at,
                error=(summary.output or {}).get("error"),
            )
        else:
            status = AnalysisStatus(status="pending" if self.p.llm else "disabled")
        imp_row = rows.get((AnalysisKind.IMPORTANCE, SCORE_VERSION))
        importance = ImportanceBreakdown(**imp_row.output) if imp_row else None
        if importance and user:
            prefs = await self.s.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
            if prefs:
                importance.personal_score, importance.personal_reasons = personalize(
                    importance.score,
                    categories=[c.slug for c in article.categories],
                    text=f"{article.title} {article.description or ''}",
                    interests=list(prefs.interests),
                    followed=[
                        *prefs.followed_technologies,
                        *prefs.followed_providers,
                        *prefs.followed_repositories,
                    ],
                )
        ent = rows.get((AnalysisKind.ENTITIES, RULES_VERSION))
        eo = ent.output if ent else {}
        return ArticleAnalysisOut(
            article_id=str(article_id),
            summary=summary.output if summary and summary.valid else None,
            summary_status=status,
            importance=importance,
            language=eo.get("language") or article.language,
            keywords=eo.get("keywords", []),
            entities=eo.get("entities", []),
        )

    async def status(self) -> AIStatus:
        now = datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        async def count(stmt) -> int:  # type: ignore[no-untyped-def]
            return int(await self.s.scalar(stmt) or 0)

        def kind(k: AnalysisKind, v: str, valid: bool = True):  # type: ignore[no-untyped-def]
            return select(func.count(AIAnalysis.id)).where(
                AIAnalysis.kind == k, AIAnalysis.prompt_version == v, AIAnalysis.valid.is_(valid)
            )

        usage = (
            await self.s.execute(
                select(
                    func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
                    func.sum(AIUsage.cost_usd),
                    func.count(AIUsage.id),
                    func.count(AIUsage.id).filter(AIUsage.ok.is_(False)),
                ).where(AIUsage.created_at >= start)
            )
        ).one()
        llm, emb = self.p.llm, self.p.embedder
        return AIStatus(
            llm_provider=llm.provider if llm else None,
            llm_model=llm.model if llm else None,
            embedding_provider=emb.provider if emb else None,
            embedding_model=emb.model if emb else None,
            problems=list(self.p.problems),
            items_total=await count(select(func.count(Article.id))),
            items_with_rules_analysis=await count(kind(AnalysisKind.ENTITIES, RULES_VERSION)),
            items_with_ai_summary=await count(kind(AnalysisKind.SUMMARY, PROMPT_VERSION)),
            items_with_embedding=await count(
                select(func.count(Article.id)).where(Article.embedding.is_not(None))
            ),
            failed_analyses=await count(kind(AnalysisKind.SUMMARY, PROMPT_VERSION, valid=False)),
            tokens_today=int(usage[0]),
            cost_today_usd=float(usage[1]) if usage[1] is not None else None,
            calls_today=int(usage[2]),
            errors_today=int(usage[3]),
        )
