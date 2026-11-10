"""Question answering over collected items, with citations - or an explicit "not enough information".

1. Interpret the question (time window, item types, technologies) with transparent rules.
2. Retrieve: hybrid (BM25 + semantic, RRF) when embeddings exist, else BM25 over FTS candidates;
   lightly boosted by AI Pulse importance and recency.
3. Sufficiency gate BEFORE calling the LLM: too few relevant sources → insufficient, no generation.
4. Generate with numbered sources only; then validate: citations must point to provided sources,
   unsupported numbers/versions/ids are removed, an answer with no valid citation is rejected.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import claims
from app.ai.pipeline import record_usage
from app.ai.prompts import SYSTEM_RAG, RagAnswer
from app.ai.providers import AIProviders, ProviderError
from app.ai.search import Hit, Retriever
from app.ai.text import TECH, clean_text, tokens
from app.models import AIAnalysis, User
from app.models.enums import AnalysisKind, ItemType, Severity
from app.schemas.article import ArticleFilters

MIN_SOURCES = 2  # one source suffices only when it fully covers the question
MIN_TERM_COVERAGE = 0.5  # share of informative question terms that must appear in the best sources
CITE_RE = re.compile(r"\[(\d{1,2})\]")
QUESTION_NOISE = set(
    "what which who when where why how are is the latest newest new recent recently important most top any "
    "this week month today there have has been were was do does did tell me about show list give happened "
    "happening developments development disclosed affecting affect popular major big things "
    "anything everything published announced reported".split()
)

TYPE_CUES: list[tuple[re.Pattern[str], list[ItemType]]] = [
    (re.compile(r"\b(vulnerab|cves?\b|security advisor|exploit)", re.I), [ItemType.VULNERABILITY]),
    (re.compile(r"\b(bugs?|regressions?|issues?|crash)", re.I), [ItemType.BUG, ItemType.GITHUB_ISSUE]),
    (re.compile(r"\b(outages?|incidents?|downtime|disruptions?)", re.I), [ItemType.INCIDENT]),
    (
        re.compile(
            r"\b(model releases?|models?\b(?:\W+\w+){0,2}?\W+(?:released|launched|announced|published)"
            r"|(?:released|launched|new) (?:\w+ )?models?)\b",
            re.I,
        ),
        [ItemType.MODEL_RELEASE, ItemType.NEWS],
    ),
    (re.compile(r"\b(papers?|research|arxiv)\b", re.I), [ItemType.RESEARCH]),
    (re.compile(r"\b(tools?|frameworks?|librar(y|ies))\b", re.I), [ItemType.TOOL, ItemType.GITHUB_REPO]),
]
# Severity words are a filter on the official severity, never a text match ("critical" in a description
# does not make an item critical).
SEVERITY_CUES: list[tuple[re.Pattern[str], list[Severity]]] = [
    (re.compile(r"\bcritical\b", re.I), [Severity.CRITICAL]),
    (re.compile(r"\b(high[- ]severity|severe|serious)\b", re.I), [Severity.CRITICAL, Severity.HIGH]),
]
SEVERITY_WORDS = {"critical", "severe", "serious", "severity", "high"}
TIME_CUES: list[tuple[re.Pattern[str], timedelta]] = [
    (re.compile(r"\btoday\b|\blast 24 ?h", re.I), timedelta(days=1)),
    (re.compile(r"\bthis week\b|\bpast week\b|\blast 7 days\b|\blast week\b", re.I), timedelta(days=7)),
    (re.compile(r"\bthis month\b|\blast 30 days\b|\blast month\b", re.I), timedelta(days=30)),
    (re.compile(r"\b(recent(ly)?|latest|new(est)?|just)\b", re.I), timedelta(days=30)),
]


@dataclass
class Plan:
    item_types: list[ItemType] = field(default_factory=list)
    severities: list[Severity] = field(default_factory=list)
    date_from: datetime | None = None
    terms: list[str] = field(default_factory=list)
    window_days: int | None = None


def interpret(question: str, now: datetime) -> Plan:
    plan = Plan()
    cue: re.Pattern[str] | None = None
    for pattern, types in TYPE_CUES:
        if pattern.search(question):
            plan.item_types = [*plan.item_types, *[t for t in types if t not in plan.item_types]]
            cue = pattern
            break
    for pattern, delta in TIME_CUES:
        if pattern.search(question):
            plan.date_from = now - delta
            plan.window_days = delta.days
            break
    for pattern, severities in SEVERITY_CUES:
        if pattern.search(question):
            plan.severities = severities
            break
    plan.terms = [t for t in tokens(question) if t not in QUESTION_NOISE and len(t) > 2]
    if plan.severities:
        plan.terms = [t for t in plan.terms if not set(t.split("-")) & SEVERITY_WORDS]
    if cue is not None:  # the words that selected the item type are a filter now, not search terms
        plan.terms = [t for t in plan.terms if not cue.search(t)]
    if plan.item_types == [ItemType.VULNERABILITY]:
        plan.terms = [t for t in plan.terms if not t.startswith(("vulnerab", "cve", "disclos"))]
    if ItemType.BUG in plan.item_types:
        plan.terms = [t for t in plan.terms if t not in ("bugs", "bug", "affecting", "issues")]
    if ItemType.MODEL_RELEASE in plan.item_types:
        plan.terms = [
            t for t in plan.terms if t not in ("model", "models", "release", "releases", "released")
        ]
    return plan


@dataclass
class RagResult:
    question: str
    answer: str | None
    insufficient: bool
    reason: str | None
    citations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    unsupported_claims_removed: list[str]
    retrieval: dict[str, Any]
    generated_by: dict[str, str] | None
    confidence: str | None = None


def _source_card(n: int, h: Hit, summary: str | None) -> dict[str, Any]:
    a = h.article
    return {
        "n": n,
        "article_id": str(a.id),
        "title": a.title,
        "url": a.url,
        "source": a.source.name,
        "item_type": a.item_type.value,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "importance": a.importance_score,
        "relevance": h.scores,
        "ai_summary": summary,
    }


class RagService:
    def __init__(self, session: AsyncSession, providers: AIProviders, now: datetime | None = None) -> None:
        self.s = session
        self.p = providers
        self.now = now or datetime.now(UTC)

    async def _summaries(self, ids: list[Any]) -> dict[Any, str]:
        from sqlalchemy import select

        rows = await self.s.execute(
            select(AIAnalysis.article_id, AIAnalysis.output["short_summary"].astext).where(
                AIAnalysis.article_id.in_(ids),
                AIAnalysis.kind == AnalysisKind.SUMMARY,
                AIAnalysis.valid.is_(True),
            )
        )
        return {k: v for k, v in rows.tuples().all() if v}

    async def retrieve(self, question: str, filters: ArticleFilters, k: int) -> tuple[list[Hit], Plan, str]:
        plan = interpret(question, self.now)
        f = filters.model_copy(
            update={
                "item_type": filters.item_type or plan.item_types or None,
                "severity": filters.severity or plan.severities or None,
                "date_from": filters.date_from or plan.date_from,
            }
        )
        retriever = Retriever(self.s, self.p.embedder)
        query = " ".join(plan.terms) or question
        if self.p.embedder is not None:
            hits, mode = await retriever.hybrid(query, f, natural=True), "hybrid"
        else:
            hits, mode = await retriever.lexical(query, f, natural=True), "keyword+bm25"
        if not plan.terms and not hits and (plan.item_types or plan.date_from):
            # e.g. "What are the most important AI model releases this week?" - the filters ARE the query
            rows, _ = await retriever.repo.search(f.model_copy(update={"sort": "importance"}), 0, k)
            hits, mode = (
                [
                    Hit(a, (a.importance_score or 0) / 100, {"importance": a.importance_score or 0})
                    for a in rows
                ],
                "filters+importance",
            )
        # gentle prior: importance and recency break ties between similarly relevant items
        top = max((h.score for h in hits), default=0) or 1
        for h in hits:
            age_days = (self.now - (h.article.published_at or h.article.collected_at)).total_seconds() / 86400
            prior = 0.1 * ((h.article.importance_score or 0) / 100) + 0.05 * max(0.0, 1 - age_days / 30)
            h.scores["prior"] = round(prior, 4)
            h.score = h.score / top + prior
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k], plan, mode

    @staticmethod
    def informative(plan: Plan) -> list[str]:
        return [t for t in plan.terms if t in TECH or len(t) > 3]

    def coverage(self, plan: Plan, hits: list[Hit]) -> float:
        informative = self.informative(plan)
        if not informative:
            return 1.0 if hits else 0.0
        text = " ".join(f"{h.article.title} {h.article.description or ''}".lower() for h in hits[:5])
        return sum(t in text for t in informative) / len(informative)

    async def ask(
        self, question: str, filters: ArticleFilters, user: User | None, max_sources: int = 8
    ) -> RagResult:
        hits, plan, mode = await self.retrieve(question, filters, max_sources)
        summaries = await self._summaries([h.article.id for h in hits])
        sources = [_source_card(i + 1, h, summaries.get(h.article.id)) for i, h in enumerate(hits)]
        retrieval = {
            "mode": mode,
            "item_types": [t.value for t in plan.item_types],
            "severities": [x.value for x in plan.severities],
            "date_from": plan.date_from.isoformat() if plan.date_from else None,
            "terms": plan.terms,
        }
        cov = self.coverage(plan, hits)
        retrieval["term_coverage"] = round(cov, 2)

        def insufficient(reason: str) -> RagResult:
            return RagResult(question, None, True, reason, [], sources, [], retrieval, None)

        enough = len(hits) >= MIN_SOURCES or (len(hits) == 1 and cov >= 0.99)
        # With one or two informative terms, each one matters ("capital of France" must not be answered
        # from items that only mention "capital").
        needed = 1.0 if 0 < len(self.informative(plan)) <= 2 else MIN_TERM_COVERAGE
        if not enough or cov < needed:
            return insufficient(
                "Not enough collected information to answer reliably"
                + (
                    f" (only {len(hits)} relevant item{'s' if len(hits) != 1 else ''} found)"
                    if not enough
                    else " (the closest items do not cover the question's main terms)"
                )
                + ". Try a broader question or a longer time range."
            )
        llm = self.p.llm
        if llm is None:
            return RagResult(
                question,
                None,
                False,
                "AI answers are not enabled (no LLM provider configured). "
                "The most relevant collected items are listed instead.",
                [],
                sources,
                [],
                retrieval,
                None,
            )

        context = "\n\n".join(
            f"[{s['n']}] {s['title']} — {s['source']}, {s['published_at'] or 'date not stated'}\n"
            f"{clean_text((h.article.description or '') + ' ' + (h.article.content or ''), 1200)}"
            for s, h in zip(sources, hits, strict=True)
        )
        today = self.now.date().isoformat()
        prompt = f"QUESTION: {question}\nTODAY: {today}\n\nSOURCES:\n{context}\n\nAnswer as JSON."
        try:
            result = await llm.complete_json(SYSTEM_RAG, prompt, RagAnswer)
        except ProviderError as exc:
            await record_usage(
                self.s,
                "rag",
                llm.provider,
                llm.model,
                ok=False,
                error=str(exc),
                user_id=user.id if user else None,
            )
            return RagResult(
                question,
                None,
                False,
                f"The AI provider is unavailable ({exc}). Relevant items are listed instead.",
                [],
                sources,
                [],
                retrieval,
                None,
            )
        await record_usage(
            self.s,
            "rag",
            llm.provider,
            llm.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cost=result.cost_usd,
            user_id=user.id if user else None,
        )
        gen = {"provider": result.provider, "model": result.model}
        data = result.data
        if data.insufficient:
            r = insufficient(
                data.answer or "The collected sources do not contain enough information to answer."
            )
            r.generated_by = gen
            return r
        grounding = "\n".join([question, context])
        answer, unsupported = claims.strip_unsupported(data.answer, grounding)
        cited = sorted({int(n) for n in CITE_RE.findall(answer)})
        valid = [n for n in cited if 1 <= n <= len(sources)]
        answer = CITE_RE.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", answer).strip()
        if not valid or not answer:
            r = insufficient(
                "The generated answer could not be tied to the collected sources, so it was withheld."
            )
            r.generated_by, r.unsupported_claims_removed = gen, unsupported
            return r
        citations = [sources[n - 1] for n in valid]
        return RagResult(
            question, answer, False, None, citations, sources, unsupported, retrieval, gen, data.confidence
        )
