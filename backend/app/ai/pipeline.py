"""AI processing pipeline for collected items.

Stage A (deterministic, every item, no LLM):
  1 content cleaning · 2 language detection · 3 category classification (rules) · 4 keyword extraction
  5 entity extraction · 6 duplicate detection (title trigram similarity) · 7 importance scoring
Stage B (embedding provider, every item): embeddings for semantic search + embedding-based duplicate check
Stage C (LLM, most important items first, token-budgeted):
  8 summarisation · 9 technical impact · 10 learning topics (+ curated links), AI categories/entities merged.
  Output is checked against the source text: unsupported numbers/versions/ids are removed and recorded;
  vulnerability actions are kept only when an official remediation exists.

Original content is never modified; everything generated is stored in `ai_analyses`.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from prometheus_client import Counter
from sqlalchemy import Integer, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import changes, claims
from app.ai.learning import resources_for
from app.ai.prompts import CATEGORY_SLUGS, PROMPT_VERSION, SYSTEM_ANALYST, ItemAnalysis, analysis_prompt
from app.ai.providers import AIProviders, ProviderError
from app.ai.scoring import VERSION as SCORE_VERSION
from app.ai.scoring import score_item
from app.ai.text import clean_text, detect_language, extract_entities, extract_keywords
from app.core.logging import get_logger
from app.ingestion.classify import classify
from app.models import AIAnalysis, AIUsage, Article, Category, Incident, SecurityVulnerability
from app.models.enums import AnalysisKind, ItemType, Severity
from app.repositories.intel import ACTIVE_INCIDENT_WINDOW, UNRESOLVED

log = get_logger(__name__)
RULES_VERSION = "rules-v1"
TITLE_DUP_SIMILARITY = 0.85
EMBED_DUP_DISTANCE = 0.06  # cosine distance (similarity >= 0.94)
DUP_WINDOW = timedelta(days=3)
MAX_LLM_ATTEMPTS = 3

AI_CALLS = Counter("aipulse_ai_calls_total", "LLM/embedding calls", ["purpose", "provider", "status"])
AI_TOKENS = Counter("aipulse_ai_tokens_total", "LLM tokens", ["purpose", "provider", "direction"])


@dataclass
class PipelineStats:
    processed: int = 0
    duplicates: int = 0
    embedded: int = 0
    analysed: int = 0
    analysis_failed: int = 0
    skipped_budget: bool = False
    errors: list[str] = field(default_factory=list)


def input_hash(article: Article) -> str:
    return hashlib.sha256(f"{article.content_hash}|{PROMPT_VERSION}".encode()).hexdigest()[:32]


def _article_text(a: Article) -> str:
    return clean_text("\n\n".join(filter(None, [a.title, a.description, a.content])))


async def upsert_analysis(
    session: AsyncSession, article_id: uuid.UUID, kind: AnalysisKind, version: str, **values: Any
) -> None:
    row = {
        "id": uuid.uuid4(),
        "article_id": article_id,
        "kind": kind,
        "prompt_version": version,
        "created_at": datetime.now(UTC),
        "valid": True,
        **values,
    }
    stmt = insert(AIAnalysis).values(**row)
    update = {k: stmt.excluded[k] for k in row if k not in ("id", "article_id", "kind", "prompt_version")}
    await session.execute(
        stmt.on_conflict_do_update(constraint="uq_ai_analyses_article_kind_version", set_=update)
    )


async def record_usage(
    session: AsyncSession,
    purpose: str,
    provider: str,
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float | None = None,
    ok: bool = True,
    error: str | None = None,
    article_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    session.add(
        AIUsage(
            purpose=purpose,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            ok=ok,
            error=(error or "")[:500] or None,
            article_id=article_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()  # so the daily token budget sees this call immediately
    AI_CALLS.labels(purpose, provider, "ok" if ok else "error").inc()
    if input_tokens:
        AI_TOKENS.labels(purpose, provider, "input").inc(input_tokens)
    if output_tokens:
        AI_TOKENS.labels(purpose, provider, "output").inc(output_tokens)


async def tokens_used_today(session: AsyncSession, now: datetime) -> int:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0)).where(
                AIUsage.created_at >= start
            )
        )
        or 0
    )


class AnalysisPipeline:
    def __init__(
        self,
        session: AsyncSession,
        providers: AIProviders,
        *,
        daily_budget: int | None = None,
        now: datetime | None = None,
    ) -> None:
        self.s = session
        self.p = providers
        self.daily_budget = daily_budget
        self.now = now or datetime.now(UTC)
        self._cats: dict[str, Category] | None = None

    async def _categories(self) -> dict[str, Category]:
        if self._cats is None:
            self._cats = {c.slug: c for c in await self.s.scalars(select(Category))}
        return self._cats

    async def _add_categories(self, article: Article, slugs: list[str]) -> None:
        cats = await self._categories()
        have = {c.slug for c in article.categories}
        for slug in slugs:
            if slug in cats and slug not in have:
                article.categories.append(cats[slug])
                have.add(slug)

    # ------------------------------------------------------------------ stage A
    async def _facts(self, a: Article) -> dict[str, Any]:
        """Structured facts from typed tables (used for scoring and as grounded prompt context)."""
        facts: dict[str, Any] = {}
        if a.item_type == ItemType.VULNERABILITY:
            v = await self.s.scalar(
                select(SecurityVulnerability).where(
                    or_(
                        SecurityVulnerability.article_id == a.id,
                        SecurityVulnerability.cve_id == a.external_id,
                    )
                )
            )
            if v is not None:
                facts.update(
                    cve_id=v.cve_id,
                    cvss=v.cvss_score,
                    cvss_version=v.cvss_version,
                    severity=v.severity.value,
                    known_exploited=v.known_exploited,
                    remediation=v.remediation,
                    patch_available=v.patch_available,
                    affected=[f"{p.get('vendor')}/{p.get('product')}" for p in (v.affected_products or [])][
                        :10
                    ],
                    references=[r["url"] for r in (v.references or []) if r.get("url")][:8],
                )
        elif a.item_type == ItemType.INCIDENT:
            i = await self.s.scalar(select(Incident).where(Incident.article_id == a.id))
            if i is not None:
                facts.update(
                    provider=i.provider,
                    status=i.status.value,
                    services=i.affected_services[:10],
                    incident_active=i.status in UNRESOLVED
                    and i.last_verified_at >= self.now - ACTIVE_INCIDENT_WINDOW,
                )
        return facts

    async def _title_duplicate(self, a: Article) -> uuid.UUID | None:
        if a.duplicate_of_id is not None or len(a.title) < 25:
            return None
        when = a.published_at or a.collected_at
        row = await self.s.execute(
            text("""SELECT id FROM articles WHERE id <> :id AND source_id <> :src AND item_type = :t
                    AND duplicate_of_id IS NULL AND similarity(title, :title) >= :sim
                    AND coalesce(published_at, collected_at) BETWEEN :lo AND :hi
                    AND collected_at <= :collected ORDER BY similarity(title, :title) DESC LIMIT 1"""),
            {
                "id": a.id,
                "src": a.source_id,
                "t": a.item_type.value,
                "title": a.title,
                "sim": TITLE_DUP_SIMILARITY,
                "lo": when - DUP_WINDOW,
                "hi": when + DUP_WINDOW,
                "collected": a.collected_at,
            },
        )
        hit = row.scalar()
        return hit

    async def stage_a(self, a: Article) -> dict[str, Any]:
        body = _article_text(a)
        lang = detect_language(body)
        if a.language is None and lang:
            a.language = lang
        await self._add_categories(a, classify(body, []))
        keywords = extract_keywords(body)
        entities = extract_entities(body)
        dup = await self._title_duplicate(a)
        if dup is not None:
            a.duplicate_of_id = dup
        facts = await self._facts(a)
        await upsert_analysis(
            self.s,
            a.id,
            AnalysisKind.ENTITIES,
            RULES_VERSION,
            provider="aipulse",
            model=RULES_VERSION,
            output={
                "language": lang,
                "keywords": keywords,
                "entities": entities,
                "input_hash": input_hash(a),
                "duplicate_of": str(dup) if dup else None,
            },
        )
        await self.score(a, facts)
        await self.detect_changes(a)
        return facts

    async def detect_changes(self, a: Article) -> None:
        """Release items: compare with the previous release of the same model/tool/repository."""
        try:
            async with self.s.begin_nested():
                out = await changes.detect(self.s, a)
                if out is not None:
                    await upsert_analysis(
                        self.s,
                        a.id,
                        AnalysisKind.CHANGES,
                        changes.VERSION,
                        provider="aipulse",
                        model=changes.VERSION,
                        output=out,
                    )
        except Exception as exc:  # noqa: BLE001 - a comparison problem must not stop the pipeline
            log.warning("change_detection_failed", article_id=str(a.id), error=f"{type(exc).__name__}: {exc}")

    async def score(self, a: Article, facts: dict[str, Any] | None = None) -> dict[str, Any]:
        facts = facts if facts is not None else await self._facts(a)
        impact = await self.s.scalar(
            select(AIAnalysis.output["technical_impact"]["level"].astext).where(
                AIAnalysis.article_id == a.id,
                AIAnalysis.kind == AnalysisKind.SUMMARY,
                AIAnalysis.valid.is_(True),
            )
        )
        severity, basis = a.severity, a.severity_basis
        linked = facts.get("severity")
        if severity is None and facts.get("cvss") is not None and linked not in (None, "unknown"):
            # e.g. a CISA KEV entry: the feed has no CVSS, but the linked CVE record has the official one.
            severity = Severity(facts["severity"])
            basis = f"CVSS {facts.get('cvss_version') or ''} {facts['cvss']} of linked {facts.get('cve_id')}"
        breakdown = score_item(
            item_type=a.item_type,
            reliability=a.source.reliability,
            severity=severity,
            severity_basis=basis,
            published_at=a.published_at,
            collected_at=a.collected_at,
            verification=a.verification_status,
            now=self.now,
            known_exploited=facts.get("known_exploited"),
            impact_level=impact if impact != "unknown" else None,
            incident_active=facts.get("incident_active"),
        )
        a.importance_score = breakdown["score"]
        await upsert_analysis(
            self.s,
            a.id,
            AnalysisKind.IMPORTANCE,
            SCORE_VERSION,
            provider="aipulse",
            model=SCORE_VERSION,
            output=breakdown,
        )
        return breakdown

    # ------------------------------------------------------------------ stage B
    async def embed(self, articles: list[Article], stats: PipelineStats) -> None:
        emb = self.p.embedder
        if emb is None or not articles:
            return
        texts = [clean_text(f"{a.title}\n{a.description or ''}\n{a.content or ''}", 4000) for a in articles]
        try:
            vectors, usage = await emb.embed(texts)
        except ProviderError as exc:
            stats.errors.append(f"embedding: {exc}")
            await record_usage(self.s, "embedding", emb.provider, emb.model, ok=False, error=str(exc))
            return
        await record_usage(self.s, "embedding", emb.provider, emb.model, input_tokens=usage.input_tokens)
        for a, v in zip(articles, vectors, strict=True):
            a.embedding = v
            stats.embedded += 1
        await self.s.flush()
        for a in articles:
            if a.duplicate_of_id is None:
                when = a.published_at or a.collected_at
                hit = await self.s.scalar(
                    select(Article.id)
                    .where(
                        Article.id != a.id,
                        Article.source_id != a.source_id,
                        Article.item_type == a.item_type,
                        Article.duplicate_of_id.is_(None),
                        Article.embedding.is_not(None),
                        Article.collected_at <= a.collected_at,
                        func.coalesce(Article.published_at, Article.collected_at).between(
                            when - DUP_WINDOW, when + DUP_WINDOW
                        ),
                        Article.embedding.cosine_distance(a.embedding) < EMBED_DUP_DISTANCE,
                    )
                    .order_by(Article.embedding.cosine_distance(a.embedding))
                    .limit(1)
                )
                if hit is not None:
                    a.duplicate_of_id = hit
                    stats.duplicates += 1

    # ------------------------------------------------------------------ stage C
    async def analyse(self, a: Article, facts: dict[str, Any], stats: PipelineStats) -> bool:
        llm = self.p.llm
        if llm is None:
            return False
        body = _article_text(a)
        structured = "\n".join(
            f"- {k}: {v}" for k, v in facts.items() if v not in (None, [], "") and k != "references"
        )
        remediation = facts.get("remediation") if a.item_type == ItemType.VULNERABILITY else None
        prompt = analysis_prompt(
            item_type=a.item_type.value,
            title=a.title,
            source=a.source.name,
            published=a.published_at.isoformat() if a.published_at else None,
            url=a.url,
            body=body[:8000],
            structured=structured,
            remediation=remediation,
        )
        grounding = "\n".join([a.title, body, structured, remediation or ""])
        prev = await self.s.scalar(
            select(AIAnalysis).where(
                AIAnalysis.article_id == a.id,
                AIAnalysis.kind == AnalysisKind.SUMMARY,
                AIAnalysis.prompt_version == PROMPT_VERSION,
            )
        )
        attempts = int((prev.output or {}).get("attempts", 0)) + 1 if prev and not prev.valid else 1
        try:
            result = await llm.complete_json(SYSTEM_ANALYST, prompt, ItemAnalysis)
        except ProviderError as exc:
            stats.analysis_failed += 1
            stats.errors.append(f"{a.id}: {exc}")
            await record_usage(
                self.s, "analysis", llm.provider, llm.model, ok=False, error=str(exc), article_id=a.id
            )
            await upsert_analysis(
                self.s,
                a.id,
                AnalysisKind.SUMMARY,
                PROMPT_VERSION,
                provider=llm.provider,
                model=llm.model,
                valid=False,
                output={
                    "error": str(exc)[:500],
                    "retryable": exc.retryable,
                    "attempts": attempts,
                    "input_hash": input_hash(a),
                },
            )
            return False
        out = self.ground(a, result.data, grounding, has_remediation=bool(remediation), facts=facts)
        valid = bool(out["short_summary"])
        await record_usage(
            self.s,
            "analysis",
            llm.provider,
            llm.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost=result.cost_usd,
            article_id=a.id,
        )
        await upsert_analysis(
            self.s,
            a.id,
            AnalysisKind.SUMMARY,
            PROMPT_VERSION,
            provider=llm.provider,
            model=llm.model,
            valid=valid,
            output={**out, "attempts": attempts, "input_hash": input_hash(a)},
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost_usd=result.cost_usd,
            confidence=None,
        )
        if valid:
            await self._add_categories(a, out["categories"])
            stats.analysed += 1
        else:
            stats.analysis_failed += 1
        return valid

    def ground(
        self, a: Article, data: ItemAnalysis, grounding: str, *, has_remediation: bool, facts: dict[str, Any]
    ) -> dict[str, Any]:
        """Remove anything not supported by the source; attach references and curated learning links."""
        unsupported: set[str] = set()
        fields = {}
        for name in (
            "short_summary",
            "detailed_explanation",
            "what_happened",
            "why_it_matters",
            "who_is_affected",
        ):
            kept, bad = claims.strip_unsupported(getattr(data, name), grounding)
            fields[name] = kept
            unsupported.update(bad)
        if not fields["short_summary"]:  # the summary sentence carried an unsupported claim: fall back
            fields["short_summary"] = fields["what_happened"][:400]
        impact_desc, bad = claims.strip_unsupported(data.technical_impact.description, grounding)
        unsupported.update(bad)
        actions, dropped = claims.filter_actions(
            data.recommended_actions,
            grounding,
            has_trusted_remediation=has_remediation or a.item_type != ItemType.VULNERABILITY,
        )
        if a.item_type == ItemType.VULNERABILITY and not has_remediation:
            actions = [
                *actions,
                "No official remediation was published in the collected sources; follow the vendor advisory.",
            ]
        categories = [c for c in dict.fromkeys(data.categories) if c in CATEGORY_SLUGS]
        refs = [a.url, *[u for u in facts.get("references", []) if u != a.url]][:6]
        return {
            **fields,
            "technical_impact": {"level": data.technical_impact.level, "description": impact_desc},
            "recommended_actions": actions,
            "related_technologies": data.related_technologies[:10],
            "categories": categories,
            "entities": [e.model_dump() for e in data.entities],
            "learning_resources": resources_for(
                categories or [c.slug for c in a.categories], data.learning_topics
            ),
            "source_references": refs,  # set by AI Pulse, never by the model
            "unsupported_claims_removed": sorted(unsupported),
            "actions_removed": dropped,
            "ai_generated": True,
        }

    # ------------------------------------------------------------------ orchestration
    async def pending_stage_a(self, limit: int) -> list[Article]:
        done = select(AIAnalysis.article_id).where(
            AIAnalysis.kind == AnalysisKind.ENTITIES, AIAnalysis.prompt_version == RULES_VERSION
        )
        return list(
            (
                await self.s.scalars(
                    select(Article)
                    .where(Article.id.not_in(done))
                    .order_by(Article.collected_at.desc())
                    .limit(limit)
                )
            )
            .unique()
            .all()
        )

    async def pending_llm(self, limit: int) -> list[Article]:
        ok = select(AIAnalysis.article_id).where(
            AIAnalysis.kind == AnalysisKind.SUMMARY,
            AIAnalysis.prompt_version == PROMPT_VERSION,
            or_(
                AIAnalysis.valid.is_(True),
                func.coalesce(AIAnalysis.output["attempts"].astext.cast(Integer), 0) >= MAX_LLM_ATTEMPTS,
            ),
        )
        return list(
            (
                await self.s.scalars(
                    select(Article)
                    .where(Article.duplicate_of_id.is_(None), Article.id.not_in(ok))
                    .order_by(Article.importance_score.desc().nulls_last(), Article.collected_at.desc())
                    .limit(limit)
                )
            )
            .unique()
            .all()
        )

    async def run(
        self,
        *,
        stage_a_limit: int = 500,
        llm_limit: int = 20,
        embed_limit: int = 200,
        article_ids: list[uuid.UUID] | None = None,
    ) -> PipelineStats:
        stats = PipelineStats()
        if article_ids:
            items = list(
                (await self.s.scalars(select(Article).where(Article.id.in_(article_ids)))).unique().all()
            )
        else:
            items = await self.pending_stage_a(stage_a_limit)
        facts: dict[uuid.UUID, dict[str, Any]] = {}
        for a in items:
            facts[a.id] = await self.stage_a(a)
            stats.processed += 1
            stats.duplicates += int(a.duplicate_of_id is not None)
        await self.s.flush()

        if self.p.embedder is not None:
            to_embed = list(
                (
                    await self.s.scalars(
                        select(Article)
                        .where(Article.embedding.is_(None))
                        .order_by(Article.collected_at.desc())
                        .limit(embed_limit)
                    )
                )
                .unique()
                .all()
            )
            await self.embed(to_embed, stats)

        if self.p.llm is not None and llm_limit > 0:
            if (
                self.daily_budget is not None
                and await tokens_used_today(self.s, self.now) >= self.daily_budget
            ):
                stats.skipped_budget = True
            else:
                for a in await self.pending_llm(llm_limit):
                    f = facts.get(a.id) or await self._facts(a)
                    if await self.analyse(a, f, stats):
                        await self.score(a, f)  # impact level now known
                    if (
                        self.daily_budget is not None
                        and await tokens_used_today(self.s, self.now) >= self.daily_budget
                    ):
                        stats.skipped_budget = True
                        break
        await self.s.flush()
        log.info(
            "ai_pipeline_done",
            **{k: v for k, v in stats.__dict__.items() if k != "errors"},
            errors=len(stats.errors),
        )
        return stats
