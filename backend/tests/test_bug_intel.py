"""Bug Intelligence: cited facts from official sources, grounded AI text, "insufficient information"."""

from datetime import date

from sqlalchemy import select

from app.ai.bugintel import INSUFFICIENT, BugIntelligence, product_line
from app.models import AIAnalysis, Article, GitHubIssue, GitHubRepository, SecurityVulnerability, SoftwareBug
from app.models.enums import AnalysisKind, BugKind, IssueState, ItemType, Severity
from tests import feature_data as fd
from tests.ai_fakes import ScriptedChat, providers
from tests.conftest import register_and_login

CVE = "CVE-2026-41111"


async def _cve(session_factory):
    async with session_factory() as s:
        nvd = await fd.source(s, "nvd-src", connector="nvd", name="NVD")
        gha = await fd.source(s, "gha-src", connector="github_advisories", name="GitHub Advisories")
        rel = await fd.source(s, "rel-src", connector="github_releases", name="GitHub releases")
        item = await fd.article(
            s, nvd, CVE, item_type=ItemType.VULNERABILITY, title=f"{CVE}: path traversal in Acme Widget",
            description="A path traversal in the upload handler of Acme Widget lets a remote attacker read files.",
            url=f"https://nvd.nist.gov/vuln/detail/{CVE}", canonical_key=f"cve:{CVE}",
        )  # fmt: skip
        s.add(SecurityVulnerability(
            article_id=item.id, cve_id=CVE, severity=Severity.CRITICAL, cvss_score=9.8, cvss_version="3.1",
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", cwe_ids=["CWE-22"],
            description="A path traversal in the upload handler of Acme Widget lets a remote attacker read files.",
            affected_products=[{"vendor": "acme", "product": "widget", "versionStartIncluding": "2.0",
                                "versionEndExcluding": "2.4.1"}],
            known_exploited=True, kev_date_added=date(2026, 11, 9),
        ))  # fmt: skip
        adv = await fd.article(s, gha, "ghsa", item_type=ItemType.VULNERABILITY, title="GHSA-xxxx: Acme Widget",
                               content="Upgrade acme-widget to 2.4.1 or later.", canonical_key=f"cve:{CVE}",
                               duplicate_of_id=item.id)  # fmt: skip
        notes = await fd.article(s, rel, "widget-241", item_type=ItemType.TOOL, title="acme/widget v2.4.1",
                                 content=f"## Security\n- Fix path traversal in uploads ({CVE})",
                                 canonical_key="gh-release:acme/widget:v2.4.1")  # fmt: skip
        other = await fd.article(s, rel, "other", title="Unrelated news")
        await s.commit()
        return item.id, adv.id, notes.id, other.id


async def test_facts_are_cited_from_official_sources_without_an_llm(client, session_factory):
    item, adv, notes, _ = await _cve(session_factory)
    r = await client.get(f"/api/v1/news/{item}/bug-intelligence")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "facts_only" and out["ai_generated"] is False and out["llm_available"] is False
    assert out["subject"] == {**out["subject"], "kind": "vulnerability", "id": CVE}
    src = {s["n"]: s for s in out["sources"]}
    kinds = [s["kind"] for s in out["sources"]]
    assert kinds == ["cve_record", "cve_record", "advisory", "release_notes"]
    assert src[4]["url"].endswith("/widget-241")

    sec = out["sections"]
    assert sec["cause"]["facts"] == [{"text": "Weakness: CWE-22", "citation": 2}]
    impact = [f["text"] for f in sec["impact"]["facts"]]
    assert impact[0].startswith("CVSS 9.8 (critical)") and "CISA KEV since 2026-11-09" in impact[1]
    assert sec["affected_versions"]["facts"] == [{"text": "acme widget >= 2.0 < 2.4.1", "citation": 2}]
    assert sec["fixes"]["facts"] == [
        {"text": "Mentioned in the release notes of acme/widget v2.4.1", "citation": 4}
    ]
    assert all(s["status"] == "documented" and s["text_is_ai"] is False for s in sec.values())


async def test_ai_text_is_grounded_cited_and_never_invents_a_fix(client, session_factory):
    item, *_ = await _cve(session_factory)
    reply = {
        "cause": {"text": "The upload handler does not normalise paths. It was introduced in 9.9.9.",
                  "citations": [1, 2]},
        "impact": {"text": "A remote attacker can read files.", "citations": [99]},  # no valid source
        "affected_versions": {"text": None, "citations": []},
        "fixes": {"text": "Upgrade to 2.4.1 or later.", "citations": [4]},
    }  # fmt: skip
    client._transport.app.state.ai_providers = providers(chat=ScriptedChat(default=reply))  # type: ignore[attr-defined]
    h = {"Authorization": f"Bearer {await register_and_login(client, 'bugs@example.com')}"}
    r = await client.post(f"/api/v1/news/{item}/bug-intelligence", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    sec = out["sections"]
    assert out["status"] == "ready" and out["ai_generated"] is True and out["provider"] == "fake"
    assert (
        sec["cause"]["text"] == "The upload handler does not normalise paths."
    )  # unsupported version removed
    assert sec["cause"]["citations"] == [1, 2] and out["unsupported_claims_removed"] == ["9.9.9"]
    assert (
        sec["impact"]["text"] is None and sec["impact"]["citations"] == []
    )  # uncited text dropped, facts stay
    assert sec["fixes"]["text"] == "Upgrade to 2.4.1 or later." and sec["fixes"]["text_is_ai"]

    # Stored, and served by GET from then on.
    again = (await client.get(f"/api/v1/news/{item}/bug-intelligence")).json()
    assert again["sections"] == sec and again["llm_available"] is True
    async with session_factory() as s:
        assert await s.scalar(select(AIAnalysis).where(AIAnalysis.kind == AnalysisKind.BUG_INTEL))


async def test_a_fix_is_kept_only_when_a_cited_source_documents_one(session_factory):
    item, *_ = await _cve(session_factory)
    reply = {"fixes": {"text": "Upgrade to 2.4.1 or later.", "citations": [1]}}  # the NVD record has no fix
    async with session_factory() as s:
        a = await s.get(Article, item)
        out = await BugIntelligence(s, providers(chat=ScriptedChat(default=reply))).build(a, use_llm=True)
    assert out["sections"]["fixes"]["text"] is None
    assert out["sections"]["fixes"]["facts"]  # the release-notes fact is still shown, with its citation


async def test_insufficient_information_when_sources_are_silent(client, session_factory):
    async with session_factory() as s:
        gh = await fd.source(s, "gh-bugs", connector="github_issues", name="GitHub issues")
        a = await fd.article(s, gh, "issue-7", item_type=ItemType.BUG, title="Crash on startup",
                             url="https://github.com/acme/tool/issues/7")  # fmt: skip
        repo = GitHubRepository(full_name="acme/tool", html_url="https://github.com/acme/tool")
        s.add(repo)
        await s.flush()
        issue = GitHubIssue(repository_id=repo.id, number=7, title="Crash on startup", html_url=a.url,
                            state=IssueState.OPEN, opened_at=fd.NOW)  # fmt: skip
        s.add(issue)
        await s.flush()
        s.add(SoftwareBug(article_id=a.id, github_issue_id=issue.id, project="acme/tool", kind=BugKind.BUG,
                          severity=Severity.UNKNOWN, status=IssueState.OPEN, source_url=a.url))  # fmt: skip
        news = await fd.article(s, gh, "news", title="Not a bug")
        await s.commit()
    out = (await client.get(f"/api/v1/news/{a.id}/bug-intelligence")).json()
    assert out["subject"]["id"] == "acme/tool#7"
    for key in ("cause", "impact", "affected_versions", "fixes"):
        assert out["sections"][key] == {"status": "insufficient", "text": INSUFFICIENT, "text_is_ai": False,
                                        "citations": [], "facts": []}  # fmt: skip
    assert (await client.get(f"/api/v1/news/{news.id}/bug-intelligence")).status_code == 400
    h = {"Authorization": f"Bearer {await register_and_login(client, 'nollm@example.com')}"}
    assert (await client.post(f"/api/v1/news/{a.id}/bug-intelligence", headers=h)).status_code == 400


def test_product_lines_keep_the_source_ranges():
    assert product_line({"vendor": "acme", "product": "x", "version": "1.2"}) == "acme x 1.2"
    assert product_line({"ecosystem": "pip", "product": "y", "vulnerable_range": "< 3.1"}) == "pip y < 3.1"
