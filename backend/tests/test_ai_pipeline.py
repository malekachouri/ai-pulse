"""Pipeline, RAG and briefing against the real DB with scripted providers."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.ai.briefing import BriefingGenerator, due_briefings
from app.ai.pipeline import AnalysisPipeline
from app.ai.prompts import PROMPT_VERSION
from app.ai.providers import ProviderError
from app.ai.rag import RagService
from app.models import (
    AIAnalysis,
    AIUsage,
    Article,
    Category,
    SecurityVulnerability,
    Source,
    User,
    UserPreference,
)
from app.models.enums import AnalysisKind, ItemType, Severity, SourceType, VerificationStatus
from app.schemas.article import ArticleFilters
from tests.ai_fakes import ScriptedChat, analysis_reply, providers

NOW = datetime.now(UTC)


@pytest.fixture
async def corpus(session_factory):
    """Synthetic items covering the example questions."""
    async with session_factory() as s:
        cats = {c.slug: c for c in await s.scalars(select(Category))}
        src = Source(
            slug="t",
            name="Test official",
            source_type=SourceType.API,
            connector="rss",
            url="https://t.test/f",
            default_item_type=ItemType.NEWS,
            is_official=True,
            reliability=0.9,
        )
        other = Source(
            slug="o",
            name="Other",
            source_type=SourceType.RSS,
            connector="rss",
            url="https://o.test/f",
            default_item_type=ItemType.NEWS,
            is_official=True,
            reliability=0.7,
        )
        s.add_all([src, other])
        await s.flush()
        rows = [
            (
                "k8s-cve",
                ItemType.VULNERABILITY,
                "CVE-2026-116472: ingress-nginx mirror-target self-DOS in Kubernetes",
                "A security issue was discovered in ingress-nginx where a user can cause denial of service.",
                Severity.LOW,
                "Kubernetes SRC CVSS v3.1 2.7",
                ["kubernetes", "cybersecurity"],
                2,
            ),
            (
                "k8s-cve2",
                ItemType.VULNERABILITY,
                "CVE-2026-116500: Kubernetes kubelet path traversal",
                "Kubernetes kubelet allows path traversal; fixed in 1.31.4.",
                Severity.HIGH,
                "Kubernetes SRC CVSS v3.1 7.1",
                ["kubernetes", "cybersecurity"],
                5,
            ),
            (
                "rag1",
                ItemType.RESEARCH,
                "Sparse retrieval heads improve long-context RAG",
                "We study retrieval-augmented generation (RAG) with sparse attention heads.",
                None,
                None,
                ["rag", "ai-research"],
                20,
            ),
            (
                "rag2",
                ItemType.NEWS,
                "New RAG evaluation toolkit released",
                "An open RAG benchmark for retrieval pipelines.",
                None,
                None,
                ["rag"],
                10,
            ),
            (
                "old",
                ItemType.NEWS,
                "Ancient cloud news",
                "Something about AWS from long ago.",
                None,
                None,
                ["cloud"],
                24 * 40,
            ),
            (
                "model",
                ItemType.MODEL_RELEASE,
                "Meta published Llama-5-8B on Hugging Face",
                "New model repository.",
                None,
                None,
                ["ai-models"],
                12,
            ),
        ]
        ids = {}
        for ext, t, title, desc, sev, basis, cs, hours in rows:
            a = Article(
                source_id=src.id,
                external_id=ext,
                item_type=t,
                title=title,
                description=desc,
                url=f"https://t.test/{ext}",
                published_at=NOW - timedelta(hours=hours),
                collected_at=NOW - timedelta(hours=hours),
                content_hash=ext.ljust(64, "x"),
                verification_status=VerificationStatus.OFFICIAL,
                severity=sev,
                severity_basis=basis,
                categories=[cats[c] for c in cs],
            )
            s.add(a)
            await s.flush()
            ids[ext] = a.id
        s.add(
            SecurityVulnerability(
                cve_id="CVE-2026-116472",
                severity=Severity.LOW,
                cvss_score=2.7,
                article_id=ids["k8s-cve"],
                known_exploited=False,
                remediation=None,
            )
        )
        # near-duplicate title from another source
        dup = Article(
            source_id=other.id,
            external_id="dup",
            item_type=ItemType.NEWS,
            title="New RAG evaluation toolkit released!",
            url="https://o.test/dup",
            published_at=NOW - timedelta(hours=29),
            collected_at=NOW - timedelta(hours=1),
            content_hash="d" * 64,
            verification_status=VerificationStatus.OFFICIAL,
            categories=[cats["rag"]],
        )
        s.add(dup)
        await s.commit()
        ids["dup"] = dup.id
        return ids


async def test_deterministic_stage_without_llm(session_factory, corpus):
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers()).run()
        await s.commit()
    assert stats.processed == 7 and stats.analysed == 0
    async with session_factory() as s:
        dup = await s.get(Article, corpus["dup"])
        cve = await s.get(Article, corpus["k8s-cve"])
        old = await s.get(Article, corpus["old"])
        ent = await s.scalar(
            select(AIAnalysis).where(
                AIAnalysis.article_id == cve.id, AIAnalysis.kind == AnalysisKind.ENTITIES
            )
        )
        assert dup.duplicate_of_id == corpus["rag2"]  # near-identical title, other source, within 3 days
        assert cve.language == "en" and cve.importance_score > old.importance_score
        assert {"type": "cve", "value": "CVE-2026-116472"} in ent.output["entities"]
        assert (
            await s.scalar(select(func.count(AIAnalysis.id)).where(AIAnalysis.kind == AnalysisKind.SUMMARY))
            == 0
        )
        # running again is a no-op for stage A
        assert (await AnalysisPipeline(s, providers()).run()).processed == 0


async def test_llm_analysis_grounded_and_idempotent(session_factory, corpus):
    reply = analysis_reply(
        short_summary="Kubernetes fixed a denial of service in ingress-nginx affecting 40% of clusters.",
        recommended_actions=["Upgrade ingress-nginx to v1.12.0", "Review the vendor advisory."],
    )
    chat = ScriptedChat(default=reply)
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers(chat)).run(article_ids=[corpus["k8s-cve"]], llm_limit=1)
        await s.commit()
    assert stats.analysed == 1 and len(chat.calls) == 1
    assert "TRUSTED REMEDIATION: none provided" in chat.calls[0]["user"]
    async with session_factory() as s:
        row = await s.scalar(
            select(AIAnalysis).where(
                AIAnalysis.article_id == corpus["k8s-cve"], AIAnalysis.kind == AnalysisKind.SUMMARY
            )
        )
        a = await s.get(Article, corpus["k8s-cve"])
        out = row.output
        assert row.valid and row.prompt_version == PROMPT_VERSION and row.input_tokens == 100 and row.cost_usd
        assert out["short_summary"] == "" or "40%" not in out["short_summary"]
        assert "40%" in out["unsupported_claims_removed"]
        assert all(
            "Upgrade" not in x for x in out["recommended_actions"]
        )  # no official remediation -> no fix invented
        assert any("No official remediation" in x for x in out["recommended_actions"])
        assert out["source_references"][0] == a.url and "not-a-category" not in out["categories"]
        assert all(r["url"] is None or r["source"] == "curated" for r in out["learning_resources"])
        assert await s.scalar(select(func.count(AIUsage.id)).where(AIUsage.purpose == "analysis")) == 1
    async with session_factory() as s:  # second run: nothing pending for this article
        await AnalysisPipeline(s, providers(chat)).run(article_ids=[corpus["k8s-cve"]], llm_limit=1)
    assert len(chat.calls) == 2  # the next pending article was analysed; this one was not re-sent
    assert all("CVE-2026-116472: ingress" not in c["user"].split("Title:")[1][:60] for c in chat.calls[1:])


async def test_llm_errors_are_recorded_and_pipeline_continues(session_factory, corpus):
    chat = ScriptedChat([ProviderError("upstream 503", retryable=True), "garbage", "still garbage"])
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers(chat)).run(llm_limit=2)
        await s.commit()
    assert stats.analysis_failed == 2 and stats.processed == 7  # deterministic stage still ran for everything
    async with session_factory() as s:
        rows = (await s.scalars(select(AIAnalysis).where(AIAnalysis.kind == AnalysisKind.SUMMARY))).all()
        assert len(rows) == 2 and not any(r.valid for r in rows)
        assert all(r.output["error"] for r in rows)  # reason stored for every failure
        assert all(r.output["attempts"] == 1 for r in rows)
        assert await s.scalar(select(func.count(Article.id)).where(Article.importance_score.is_(None))) == 0
        assert await s.scalar(select(func.count(AIUsage.id)).where(AIUsage.ok.is_(False))) == 2


async def test_token_budget_stops_llm(session_factory, corpus):
    chat = ScriptedChat(default=analysis_reply())
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers(chat), daily_budget=100).run(llm_limit=5)
    assert len(chat.calls) == 1 and stats.skipped_budget  # 150 tokens used > 100 budget


async def test_embeddings_semantic_dedup(session_factory, corpus):
    async with session_factory() as s:
        stats = await AnalysisPipeline(s, providers(embed=True)).run()
        await s.commit()
    assert stats.embedded == 7
    async with session_factory() as s:
        assert await s.scalar(select(func.count(Article.id)).where(Article.embedding.is_not(None))) == 7


# ------------------------------------------------------------------ RAG
async def _prepare(session_factory, embed=False):
    async with session_factory() as s:
        await AnalysisPipeline(s, providers(embed=embed)).run()
        await s.commit()


async def test_rag_cites_sources_and_strips_unsupported(session_factory, corpus):
    await _prepare(session_factory)

    def answer(prompt):
        assert "[1]" in prompt and "SOURCES" in prompt
        return {
            "answer": "Two Kubernetes CVEs were disclosed [1][2]. One is fixed in 1.31.4 [1]. Over 70% of clusters are hit [9].",
            "confidence": "medium",
        }

    chat = ScriptedChat(default=answer)
    async with session_factory() as s:
        r = await RagService(s, providers(chat)).ask(
            "Which Kubernetes vulnerabilities were recently disclosed?", ArticleFilters(), None
        )
    assert not r.insufficient and r.answer and r.retrieval["item_types"] == ["vulnerability"]
    assert "70%" in r.unsupported_claims_removed and "[9]" not in r.answer
    assert {c["n"] for c in r.citations} <= {1, 2} and all(
        c["url"].startswith("https://t.test/") for c in r.citations
    )
    assert {s_["item_type"] for s_ in r.sources} == {"vulnerability"}


async def test_rag_insufficient_without_calling_llm(session_factory, corpus):
    await _prepare(session_factory)
    chat = ScriptedChat(default={"answer": "made up"})
    async with session_factory() as s:
        r = await RagService(s, providers(chat)).ask(
            "What happened with quantum teleportation of cats?", ArticleFilters(), None
        )
        r2 = await RagService(s, providers(chat)).ask(
            "What new bugs are affecting popular AI frameworks?", ArticleFilters(), None
        )
    assert r.insufficient and r.answer is None and "Not enough collected information" in r.reason
    assert r2.insufficient and r2.sources == []
    assert chat.calls == []  # never asked the model to improvise


async def test_rag_rejects_uncited_answers_and_honours_model_insufficient(session_factory, corpus):
    await _prepare(session_factory)
    async with session_factory() as s:
        r = await RagService(s, providers(ScriptedChat(default={"answer": "RAG is evolving quickly."}))).ask(
            "What are the latest important developments in RAG?", ArticleFilters(), None
        )
        assert r.insufficient and "could not be tied" in r.reason
        r = await RagService(
            s, providers(ScriptedChat(default={"answer": "The sources don't say.", "insufficient": True}))
        ).ask("What are the latest important developments in RAG?", ArticleFilters(), None)
        assert r.insufficient and r.generated_by["provider"] == "fake"


async def test_rag_without_llm_returns_sources_and_provider_failure_is_graceful(session_factory, corpus):
    await _prepare(session_factory)
    async with session_factory() as s:
        r = await RagService(s, providers()).ask(
            "What are the latest important developments in RAG?", ArticleFilters(), None
        )
        assert r.answer is None and not r.insufficient and r.sources and "not enabled" in r.reason
        r = await RagService(s, providers(ScriptedChat([ProviderError("timeout", retryable=True)]))).ask(
            "What are the latest important developments in RAG?", ArticleFilters(), None
        )
        assert r.answer is None and "unavailable" in r.reason and r.sources


async def test_hybrid_retrieval_with_embeddings(session_factory, corpus):
    await _prepare(session_factory, embed=True)
    chat = ScriptedChat(
        default={"answer": "A RAG toolkit and a paper were published [1][2].", "confidence": "high"}
    )
    async with session_factory() as s:
        r = await RagService(s, providers(chat, embed=True)).ask(
            "What are the latest important developments in RAG?", ArticleFilters(), None
        )
    assert r.retrieval["mode"] == "hybrid" and r.answer
    assert all("rrf" in c["relevance"] for c in r.citations)
    titles = " ".join(c["title"] for c in r.sources)
    assert "RAG" in titles and "Ancient" not in titles  # 30-day window from "latest"


# ------------------------------------------------------------------ briefings
async def test_briefing_personalised_and_idempotent(session_factory, corpus):
    await _prepare(session_factory)
    async with session_factory() as s:
        u = User(email="b@example.com", password_hash="x", role_id=3)
        s.add(u)
        await s.flush()
        s.add(UserPreference(user_id=u.id, interests=["rag"], followed_technologies=["ingress-nginx"]))
        await s.commit()
        uid = u.id
    chat = ScriptedChat(
        default={
            "executive_summary": "RAG tooling advanced [1] and an ingress-nginx CVE appeared [2]. 99% of users affected."
        }
    )
    async with session_factory() as s:
        user = await s.get(User, uid)
        b = await BriefingGenerator(s, providers(chat), NOW).generate(user)
        await s.commit()
        assert b.llm_provider == "fake" and "99%" not in b.executive_summary
        sec = b.sections
        assert {
            "top_ai",
            "new_tools",
            "research",
            "vulnerabilities",
            "bugs",
            "devops",
            "changes",
            "learning",
        } <= set(sec)
        assert sec["vulnerabilities"] and sec["vulnerabilities"][0]["title"].startswith(
            "CVE-2026-116500"
        )  # high > low
        rag = [i for i in sec["top_ai"] if "RAG" in i["title"]][0]
        assert rag["why_for_you"] and rag["personal_score"] > rag["importance"]
        assert any(c["title"].startswith("Research papers") for c in sec["changes"])
        assert all(i["url"].startswith("https://") for k in ("top_ai", "research") for i in sec[k])
        assert all(t["url"] is None or t["source"] == "curated" for t in sec["learning"])
        assert str(corpus["old"]) not in b.cited_article_ids  # outside the period
        b2 = await BriefingGenerator(s, providers(), NOW + timedelta(minutes=5)).generate(user)
        await s.commit()
        assert b2.id == b.id and b2.llm_provider is None  # same day -> replaced, deterministic summary
        assert "highlighted items" in b2.executive_summary


async def test_due_briefings_respect_timezone_and_frequency(session_factory):
    async with session_factory() as s:
        users = []
        for i, (tz, hour, freq) in enumerate(
            [("Europe/Paris", 13, "daily"), ("UTC", 13, "daily"), ("Asia/Tokyo", 8, "off")]
        ):
            u = User(email=f"d{i}@example.com", password_hash="x", role_id=3)
            s.add(u)
            await s.flush()
            s.add(UserPreference(user_id=u.id, timezone=tz, briefing_hour=hour, briefing_frequency=freq))
            users.append(u.id)
        await s.commit()
        now = datetime(2026, 11, 9, 12, 5, tzinfo=UTC)  # 13:05 in Paris, 12:05 UTC, a Monday
        due = await due_briefings(s, now)
        ids = [d.user_id for d in due]
        assert users[0] in ids and users[1] not in ids and users[2] not in ids and None in ids


async def test_kev_item_scored_with_linked_cvss_severity(session_factory, corpus):
    """A KEV entry carries no CVSS; the score uses the linked CVE record's official severity, with its basis."""
    async with session_factory() as s:
        src_id = (await s.get(Article, corpus["old"])).source_id
        cats = {c.slug: c for c in await s.scalars(select(Category))}
        kev = Article(source_id=src_id, external_id="CVE-2026-55555", item_type=ItemType.VULNERABILITY,
                      title="CVE-2026-55555 added to CISA KEV", url="https://t.test/kev",
                      published_at=NOW - timedelta(hours=2), collected_at=NOW - timedelta(hours=2),
                      content_hash="k" * 64, verification_status=VerificationStatus.OFFICIAL,
                      categories=[cats["cybersecurity"]])  # fmt: skip
        s.add(kev)
        await s.flush()
        s.add(SecurityVulnerability(cve_id="CVE-2026-55555", severity=Severity.CRITICAL, cvss_score=9.8,
                                    cvss_version="3.1", known_exploited=True, article_id=kev.id))  # fmt: skip
        await s.commit()
        await AnalysisPipeline(s, providers()).run()
        await s.commit()
        imp = await s.scalar(select(AIAnalysis).where(AIAnalysis.article_id == kev.id,
                                                      AIAnalysis.kind == AnalysisKind.IMPORTANCE))  # fmt: skip
    sev = next(f for f in imp.output["factors"] if f["name"] == "severity")
    assert sev["value"] == 1.0 and "9.8" in sev["reason"] and "CVE-2026-55555" in sev["reason"]


@pytest.mark.parametrize(
    ("question", "types", "severities", "terms"),
    [
        ("What critical Kubernetes vulnerabilities were published this week?",
         [ItemType.VULNERABILITY], [Severity.CRITICAL], ["kubernetes"]),
        ("Which AI models were released recently?", [ItemType.MODEL_RELEASE, ItemType.NEWS], [], []),
        ("Were there any GitHub outages today?", [ItemType.INCIDENT], [], ["github"]),
        ("Any high-severity bugs in vLLM?", [ItemType.BUG, ItemType.GITHUB_ISSUE],
         [Severity.CRITICAL, Severity.HIGH], ["vllm"]),
    ],
)  # fmt: skip
def test_question_interpretation(question, types, severities, terms):
    from app.ai.rag import interpret

    plan = interpret(question, NOW)
    assert (plan.item_types, plan.severities, plan.terms) == (types, severities, terms)


async def test_rag_two_term_question_needs_both_terms(session_factory, corpus):
    """Items that only share one of two terms ("capital", not "France") are not enough to answer."""
    async with session_factory() as s:
        r = await RagService(s, providers(chat=ScriptedChat([]))).ask(
            "What is the RAG capital of France?", ArticleFilters(), None
        )
    assert r.insufficient and r.answer is None
