"""Release change detection: recorded GitHub releases through ingestion, the AI pipeline and the API."""

import time
from datetime import timedelta

from sqlalchemy import select

from app.ai import changes
from app.ai.changes import (
    NOT_DOCUMENTED,
    changelog_sections,
    extract_benchmarks,
    extract_license,
    version_bump,
)
from app.ai.pipeline import AnalysisPipeline
from app.models import AIAnalysis, AIModel, AIModelRelease, Article
from app.models.enums import AnalysisKind, ItemType, VerificationStatus
from tests.ai_fakes import providers
from tests.conftest import make_admin, register_and_login  # noqa: F401 - fixtures used by the API test
from tests.ingestion_helpers import NOW, MockHttp, fixture_json, ingest, js, make_source

API = "https://api.github.com/repos/"


async def _ingest_releases(session_factory, releases):
    sid = await make_source(session_factory, "github_releases", "https://api.github.com",
                            config={"repos": [{"repo": "example-org/infer", "kind": "tool", "tool_name": "Infer",
                                               "categories": ["llmops"]}]})  # fmt: skip
    await ingest(session_factory, sid, MockHttp({f"{API}example-org/infer/releases": js(releases)}))
    async with session_factory() as s:
        await AnalysisPipeline(s, providers(), now=NOW + timedelta(days=1)).run()
        await s.commit()


async def _changes_for(session_factory, tag):
    async with session_factory() as s:
        a = await s.scalar(
            select(Article).where(Article.canonical_key == f"gh-release:example-org/infer:{tag}")
        )
        row = await s.scalar(
            select(AIAnalysis).where(AIAnalysis.article_id == a.id, AIAnalysis.kind == AnalysisKind.CHANGES)
        )
        return a, (row.output if row else None)


async def test_release_changes_from_recorded_releases(session_factory):
    await _ingest_releases(session_factory, fixture_json("github_releases_changes.json"))
    new, out = await _changes_for(session_factory, "v1.3.0")
    _, first = await _changes_for(session_factory, "v1.2.0")
    assert first is None  # the first known release has nothing to compare with

    assert out["version_change"] == {"from": "v1.2.0", "to": "v1.3.0", "bump": "minor"}
    assert out["citations"] == {
        "current": "https://github.com/example-org/infer/releases/tag/v1.3.0",
        "previous": "https://github.com/example-org/infer/releases/tag/v1.2.0",
    }
    assert out["license"]["status"] == "changed"
    assert out["license"]["previous"]["value"] == "Apache-2.0" and out["license"]["current"]["value"] == "MIT"

    bench = {b["name"]: b for b in out["benchmarks"]}
    assert bench["MMLU"]["previous"] == 71.2 and bench["MMLU"]["current"] == 73.5
    assert bench["MMLU"]["delta"] == 2.3 and bench["MMLU"]["status"] == "changed"
    assert bench["GSM8K"]["status"] == "unchanged"
    assert bench["HumanEval"] == {
        **bench["HumanEval"],
        "previous": NOT_DOCUMENTED,
        "status": "only in current",
    }
    assert "MMLU: 73.5" in bench["MMLU"]["quotes"]["current"]  # every number is quoted from its source

    sections = {s["kind"]: s for s in out["changelog"]["sections"]}
    assert sections["breaking"]["items"] == ["Removed the deprecated `--legacy-scheduler` flag"]
    assert "New OpenAI-compatible batch endpoint" in sections["features"]["items"]  # links reduced to text
    assert len(sections["fixes"]["items"]) == 2
    assert out["previous"]["title"].startswith("example-org/infer v1.2.0")


async def test_nothing_is_invented_when_sources_are_silent(session_factory):
    plain = [
        {"id": 2, "tag_name": "2.0", "html_url": "https://github.com/example-org/infer/releases/tag/2.0",
         "published_at": "2026-11-05T10:00:00Z", "body": "Maintenance release."},
        {"id": 1, "tag_name": "1.9", "html_url": "https://github.com/example-org/infer/releases/tag/1.9",
         "published_at": "2026-10-01T10:00:00Z", "body": "Maintenance release."},
    ]  # fmt: skip
    await _ingest_releases(session_factory, plain)
    _, out = await _changes_for(session_factory, "2.0")
    assert out["version_change"]["bump"] == "major"
    assert out["license"]["status"] == NOT_DOCUMENTED and out["license"]["current"]["value"] == NOT_DOCUMENTED
    assert out["benchmarks"] == [] and out["benchmarks_status"] == NOT_DOCUMENTED
    assert out["changelog"] == {"status": NOT_DOCUMENTED, "source": "current", "sections": []}


async def test_model_release_compared_with_the_previous_release_record(session_factory):
    async with session_factory() as s:
        src_id = await make_source(session_factory, "hf_models", "https://huggingface.co")
        model = AIModel(provider="Example Labs", name="Example-7B")
        s.add(model)
        await s.flush()
        art = Article(source_id=src_id, external_id="ex-7b-2", item_type=ItemType.MODEL_RELEASE,
                      title="Example-7B v2", url="https://huggingface.co/example/Example-7B-v2",
                      content="Example-7B v2 scores 64.0 on MMLU-Pro.", published_at=NOW, collected_at=NOW,
                      content_hash="m" * 64, verification_status=VerificationStatus.OFFICIAL,
                      raw={"license": "apache-2.0"})  # fmt: skip
        s.add(art)
        await s.flush()
        s.add_all([
            AIModelRelease(model_id=model.id, version="v1", released_at=NOW - timedelta(days=60),
                           source_url="https://huggingface.co/example/Example-7B", notes="MMLU-Pro 58.5"),
            AIModelRelease(model_id=model.id, version="v2", released_at=NOW, article_id=art.id,
                           source_url=art.url),
        ])  # fmt: skip
        await s.commit()
        out = await changes.detect(s, art)
    assert out["version_change"] == {"from": "v1", "to": "v2", "bump": "major"}
    mp = out["benchmarks"][0]
    assert (mp["name"], mp["previous"], mp["current"], mp["delta"]) == ("MMLU-Pro", 58.5, 64.0, 5.5)
    assert out["license"]["status"] == "documented in one source only"
    assert out["license"]["current"] == {"value": "apache-2.0", "basis": "source metadata"}
    assert out["citations"]["previous"] == "https://huggingface.co/example/Example-7B"


async def test_analysis_api_returns_the_changes(client, session_factory):
    await _ingest_releases(session_factory, fixture_json("github_releases_changes.json"))
    new, _ = await _changes_for(session_factory, "v1.3.0")
    r = await client.get(f"/api/v1/news/{new.id}/analysis")
    assert r.status_code == 200
    ch = r.json()["changes"]
    assert ch["version_change"]["to"] == "v1.3.0" and ch["method"].startswith("Rule-based")


def test_extractors():
    assert extract_benchmarks("MMLU-Pro 70.1, MMLU 85.2")["MMLU"]["value"] == 85.2
    assert extract_benchmarks("MMLU-Pro 70.1, MMLU 85.2")["MMLU-Pro"]["value"] == 70.1
    assert extract_benchmarks("90.5% on HumanEval")["HumanEval"]["value"] == 90.5
    assert extract_benchmarks("MMLU was mentioned without a score") == {}
    assert extract_license("Released under the GPL-3.0 licence? No: licensed as MIT.", None)[0] == "MIT"
    assert extract_license("", "other") == (None, None)
    assert version_bump("v0.8.5", "v0.8.6") == "patch" and version_bump("x", "y") is None
    assert changelog_sections("**Fixes**\n- one\n- two") == [
        {"heading": "Fixes", "kind": "fixes", "items": ["one", "two"]}
    ]


def test_extractors_are_linear_on_hostile_input():
    hostile = (
        "MMLU"
        + " " * 50_000
        + "\n"
        + "- "
        + "a" * 100_000
        + "\n"
        + "licensed " * 20_000
        + "\n#"
        + " " * 50_000
    )
    start = time.perf_counter()
    extract_benchmarks(hostile)
    extract_license(hostile, None)
    changelog_sections(hostile)
    assert time.perf_counter() - start < 2.0
