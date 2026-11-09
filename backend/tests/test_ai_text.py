from datetime import UTC, datetime, timedelta

from app.ai import claims
from app.ai.learning import resources_for
from app.ai.rag import interpret
from app.ai.scoring import personalize, score_item
from app.ai.search import bm25_scores, or_tsquery, rrf
from app.ai.text import clean_text, detect_language, extract_entities, extract_keywords
from app.models.enums import ItemType, Severity, VerificationStatus

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def test_clean_text():
    raw = "<p>Hello <b>world</b></p>![img](https://x/y.png) [docs](https://kubernetes.io)\n```code```\nSubscribe now!"
    assert clean_text(raw) == "Hello world docs"  # tags, image, code and boilerplate removed


def test_language_detection():
    assert (
        detect_language("The new model is available for developers and researchers around the world.") == "en"
    )
    assert (
        detect_language("Le nouveau modèle est disponible pour les développeurs et les chercheurs.") == "fr"
    )
    assert (
        detect_language("Das neue Modell ist für die Entwickler und Forscher in der Welt verfügbar.") == "de"
    )
    assert detect_language("新しいモデルが開発者向けに公開されました。研究者にも利用可能です。") == "ja"
    assert detect_language("short") is None  # unsure -> unknown, never a guess


def test_entities_only_from_text():
    t = "Kubernetes 1.31 fixes CVE-2026-1234 (CWE-79) in ingress-nginx. Meta released Llama 4 for vLLM."
    ents = {(e["type"], e["value"]) for e in extract_entities(t)}
    assert {
        ("cve", "CVE-2026-1234"),
        ("cwe", "CWE-79"),
        ("model", "Llama 4"),
        ("organization", "Meta"),
        ("technology", "vLLM"),
        ("version", "1.31"),
    } <= ents
    assert all(e["value"].lower() in t.lower() for e in extract_entities(t))
    assert "Kubernetes" in extract_keywords(t)


def test_unsupported_claims_are_stripped():
    src = "Kubernetes 1.31 fixes CVE-2026-1234. CVSS 6.5."
    text, bad = claims.strip_unsupported(
        "It fixes CVE-2026-1234 in 1.31. Upgrade to 1.31.9 now. 90% of clusters are exposed.", src
    )
    assert text == "It fixes CVE-2026-1234 in 1.31." and bad == ["1.31.9", "90%"]
    assert claims.unsupported_tokens("CVE-2026-9999 is critical", src) == ["cve-2026-9999"]


def test_remediation_only_with_trusted_source():
    src = "Upgrade ingress-nginx to v1.11.3."
    kept, dropped = claims.filter_actions(
        ["Upgrade to v1.11.3", "Monitor logs"], src, has_trusted_remediation=False
    )
    assert kept == ["Monitor logs"] and dropped == ["Upgrade to v1.11.3"]
    kept, _ = claims.filter_actions(
        ["Upgrade to v1.11.3", "Upgrade to v2.0"], src, has_trusted_remediation=True
    )
    assert kept == ["Upgrade to v1.11.3"]  # version not in the source is still dropped


def _score(**kw):
    base = dict(
        item_type=ItemType.VULNERABILITY,
        reliability=0.95,
        severity=Severity.CRITICAL,
        severity_basis="CVSS v3.1 9.8 (NVD)",
        published_at=NOW,
        collected_at=NOW,
        verification=VerificationStatus.OFFICIAL,
        now=NOW,
        known_exploited=False,
    )
    base.update(kw)
    return score_item(**base)


def test_importance_is_explainable_and_not_cvss():
    s = _score()
    assert "Not an official CVSS" in s["label"]
    assert round(sum(f["contribution"] for f in s["factors"]), 0) == round(s["score"], 0)
    assert abs(sum(f["weight"] for f in s["factors"]) - 1) < 0.01
    assert "technical_impact" in s["excluded"]  # no AI impact yet -> excluded, weights renormalised
    assert _score(known_exploited=True)["score"] > s["score"]
    assert _score(published_at=NOW - timedelta(days=9))["score"] < s["score"]
    news = _score(item_type=ItemType.NEWS, severity=None, severity_basis=None)
    assert "exploitation" in news["excluded"] and any("baseline" in f["reason"] for f in news["factors"])


def test_personalization_bonus_is_capped_and_explained():
    score, why = personalize(
        50,
        categories=["kubernetes", "rag"],
        text="vLLM on Kubernetes",
        interests=["kubernetes", "rag", "cloud"],
        followed=["vLLM"],
    )
    assert score == 65 and len(why) == 2
    assert personalize(95, categories=["rag"], text="", interests=["rag"], followed=[])[0] == 100


def test_bm25_rrf_and_safe_tsquery():
    docs = [["rag", "benchmark", "rag"], ["kubernetes", "release"], ["rag"]]
    s = bm25_scores(["rag"], docs)
    assert s[1] == 0 and s[0] > 0 and s[2] > 0
    fused = rrf([["a", "b"], ["b", "c"]])
    assert max(fused, key=fused.get) == "b"
    assert or_tsquery(["rag", "it's", "k8s", "drop;table"]) == "'rag' | 'k8s'"


def test_question_interpretation():
    p = interpret("Which Kubernetes vulnerabilities were recently disclosed?", NOW)
    assert p.item_types == [ItemType.VULNERABILITY] and p.terms == ["kubernetes"] and p.window_days == 30
    p = interpret("What are the most important AI model releases this week?", NOW)
    assert ItemType.MODEL_RELEASE in p.item_types and p.window_days == 7
    assert interpret("What new bugs are affecting popular AI frameworks?", NOW).item_types[0] == ItemType.BUG


def test_learning_links_are_curated_only():
    res = resources_for(["kubernetes"], ["Pod security"])
    assert all(r["url"] is None or r["url"].startswith("https://") for r in res)
    assert {r["source"] for r in res} == {"curated", "ai-suggested topic"}
    assert [r for r in res if r["source"] == "ai-suggested topic"][0]["url"] is None
