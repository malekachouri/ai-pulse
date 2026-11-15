"""`python -m app.cli reanalyse`: one item analysed again, nothing else taken from the backlog."""

from sqlalchemy import func, select

from app.ai.pipeline import AnalysisPipeline
from app.cli import reanalyse
from app.models import AIAnalysis
from app.models.enums import AnalysisKind, ItemType
from tests import feature_data as fd
from tests.ai_fakes import ScriptedChat, analysis_reply, providers

CVE = "CVE-2026-55555"


async def _items(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        src = await fd.source(s, "cli-src", connector="nvd", name="NVD")
        cve = await fd.article(s, src, CVE, item_type=ItemType.VULNERABILITY, title=f"{CVE}: flaw in Acme",
                               description="A flaw in Acme.", canonical_key=f"cve:{CVE}")  # fmt: skip
        other = await fd.article(s, src, "other", title="Unrelated pending news")
        await s.commit()
        return cve.id, other.id


async def _summaries(session_factory, article_id):  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        q = select(AIAnalysis).where(
            AIAnalysis.article_id == article_id, AIAnalysis.kind == AnalysisKind.SUMMARY
        )
        return list(await s.scalars(q))


async def test_reanalyse_replaces_the_summary_of_the_chosen_item_only(session_factory):
    cve, other = await _items(session_factory)
    first = ScriptedChat(default=analysis_reply(short_summary="First summary of the Acme flaw."))
    async with session_factory() as s:
        ids, stats = await reanalyse(s, providers(first), CVE.lower())  # any letter case
        await s.commit()
    assert ids == [cve] and stats is not None and stats.analysed == 1 and len(first.calls) == 1

    second = ScriptedChat(default=analysis_reply(short_summary="Second summary of the Acme flaw."))
    async with session_factory() as s:
        ids, stats = await reanalyse(s, providers(second), str(cve))  # by item id
        await s.commit()
    assert stats is not None and stats.analysed == 1
    rows = await _summaries(session_factory, cve)
    assert len(rows) == 1 and rows[0].output["short_summary"] == "Second summary of the Acme flaw."
    assert await _summaries(session_factory, other) == []  # the backlog is left to the worker


async def test_reanalyse_unknown_target_and_busy_pipeline(session_factory):
    cve, _ = await _items(session_factory)
    async with session_factory() as s:
        assert await reanalyse(s, providers(), "CVE-2000-0001") == ([], None)
        assert await reanalyse(s, providers(), "no-such-key") == ([], None)

    chat = ScriptedChat(default=analysis_reply())
    async with session_factory() as s:
        await reanalyse(s, providers(chat), CVE)
        await s.commit()
    async with session_factory() as worker, session_factory() as s:
        await AnalysisPipeline(worker, providers()).run()  # holds the lock until it commits
        ids, stats = await reanalyse(s, providers(chat), CVE)
        assert stats is not None and stats.skipped_busy
        await s.rollback()  # what the command does: the current summary is kept
        await worker.rollback()
    async with session_factory() as s:
        n = await s.scalar(
            select(func.count(AIAnalysis.id)).where(
                AIAnalysis.article_id == cve, AIAnalysis.kind == AnalysisKind.SUMMARY
            )
        )
    assert n == 1
