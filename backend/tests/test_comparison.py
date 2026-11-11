"""AI Comparison: only numbers quoted by collected sources, each with its source and date."""

from datetime import timedelta

from app.models import AIModel, AIModelRelease
from app.models.enums import ItemType
from tests import feature_data as fd


async def _models(session_factory):
    async with session_factory() as s:
        src = await fd.source(s, "model-news", name="Model news")
        hf = await fd.source(s, "hf", connector="huggingface", name="Hugging Face")
        a_new = await fd.article(
            s,
            src,
            "alpha-2",
            item_type=ItemType.MODEL_RELEASE,
            title="Alpha 2 released",
            content="Alpha 2 scores MMLU 85.2 and reaches 90.1% on HumanEval.",
            hours_ago=24,
        )
        a_old = await fd.article(
            s,
            src,
            "alpha-1",
            item_type=ItemType.MODEL_RELEASE,
            title="Alpha 1 released",
            content="Alpha 1: MMLU 80.0, GSM8K 88.0",
            hours_ago=24 * 60,
        )
        b = await fd.article(
            s,
            hf,
            "beta",
            item_type=ItemType.MODEL_RELEASE,
            title="Beta 7B",
            content="Beta 7B results: MMLU: 82.0",
            raw={"license": "apache-2.0"},
            hours_ago=48,
        )
        silent = await fd.article(s, src, "gamma", item_type=ItemType.MODEL_RELEASE, title="Gamma",
                                  content="Gamma is our fastest model yet.", hours_ago=12)  # fmt: skip
        ma = AIModel(provider="Acme AI", name="Alpha", is_open_weights=False)
        mb = AIModel(provider="Beta Labs", name="Beta 7B", is_open_weights=True)
        mg = AIModel(provider="Gamma Inc", name="Gamma")
        s.add_all([ma, mb, mg])
        await s.flush()
        s.add_all([
            AIModelRelease(model_id=ma.id, article_id=a_new.id, version="2", context_window=200000,
                           released_at=a_new.published_at, source_url=a_new.url),
            AIModelRelease(model_id=ma.id, article_id=a_old.id, version="1",
                           released_at=a_old.published_at - timedelta(hours=1), source_url=a_old.url),
            AIModelRelease(model_id=mb.id, article_id=b.id, released_at=b.published_at, source_url=b.url),
            AIModelRelease(model_id=mg.id, article_id=silent.id, released_at=silent.published_at,
                           source_url=silent.url),
        ])  # fmt: skip
        await s.commit()
        return str(ma.id), str(mb.id), str(mg.id)


async def test_compare_uses_only_cited_numbers(client, session_factory):
    a, b, _ = await _models(session_factory)
    r = await client.get("/api/v1/models/compare", params=[("ids", a), ("ids", b)])
    assert r.status_code == 200, r.text
    out = r.json()
    assert [m["name"] for m in out["models"]] == ["Alpha", "Beta 7B"]  # the order picked

    rows = {row["name"]: row for row in out["benchmarks"]}
    assert list(rows)[0] == "MMLU" and rows["MMLU"]["reported_by"] == 2
    alpha_mmlu = rows["MMLU"]["cells"][a]
    assert alpha_mmlu["value"] == 85.2 and alpha_mmlu["version"] == "2"  # newest release wins over 80.0
    assert alpha_mmlu["source_url"].endswith("/alpha-2") and "MMLU 85.2" in alpha_mmlu["quote"]
    assert alpha_mmlu["date"] is not None
    assert rows["HumanEval"]["cells"] == {a: rows["HumanEval"]["cells"][a], b: None}  # not reported: no value
    assert rows["GSM8K"]["cells"][a]["value"] == 88.0 and rows["GSM8K"]["cells"][a]["version"] == "1"
    assert "not report" in out["note"]

    alpha, beta = out["models"]
    assert alpha["context_window"]["value"] == "200,000 tokens" and alpha["context_window"]["source_url"]
    assert beta["license"] == {**beta["license"], "value": "apache-2.0", "basis": "source metadata"}
    assert alpha["latest_release"]["value"] == "2" and alpha["releases_considered"] == 2
    # Every number comes with a source.
    for row in out["benchmarks"]:
        for cell in row["cells"].values():
            assert cell is None or (cell["source_url"].startswith("https://") and cell["quote"])


async def test_no_benchmarks_and_validation(client, session_factory):
    a, _, g = await _models(session_factory)
    out = (await client.get("/api/v1/models/compare", params=[("ids", g), ("ids", g), ("ids", a)])).json()
    assert len(out["models"]) == 2  # duplicates ignored
    assert all(row["cells"][g] is None for row in out["benchmarks"])
    assert out["models"][0]["benchmarks_reported"] == 0

    assert (await client.get("/api/v1/models/compare", params=[("ids", a)])).status_code == 422
    assert (await client.get("/api/v1/models/compare", params=[("ids", a), ("ids", a)])).status_code == 400
    unknown = "00000000-0000-0000-0000-000000000001"
    assert (
        await client.get("/api/v1/models/compare", params=[("ids", a), ("ids", unknown)])
    ).status_code == 404
