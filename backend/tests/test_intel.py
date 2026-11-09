"""Integration tests for the typed intelligence modules, search and their shared list semantics."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import (
    AIModel,
    AIModelRelease,
    AITool,
    GitHubIssue,
    GitHubRepository,
    Incident,
    ResearchPaper,
    SecurityVulnerability,
    SoftwareBug,
)
from app.models.enums import BugKind, IncidentStatus, IssueState, Severity

NOW = datetime.now(UTC)


@pytest.fixture
async def intel(session_factory, seeded):
    """Structured rows linked to the synthetic articles from `seeded`."""
    async with session_factory() as s:
        llama = AIModel(
            provider="ExampleAI", name="Example-7B", family="example", modality=["text"], is_open_weights=True
        )
        closed = AIModel(
            provider="OtherLab", name="Other-Pro", modality=["text", "vision"], is_open_weights=False
        )
        s.add_all([llama, closed])
        await s.flush()
        s.add_all(
            [
                AIModelRelease(
                    model_id=llama.id,
                    version="1.0",
                    released_at=NOW - timedelta(days=40),
                    source_url="https://example.test/r1",
                ),
                AIModelRelease(
                    model_id=llama.id,
                    version="1.1",
                    released_at=NOW - timedelta(days=2),
                    context_window=131072,
                    source_url="https://example.test/r2",
                    article_id=seeded["a1"],
                ),
            ]
        )
        repo = GitHubRepository(
            full_name="acme/infer",
            html_url="https://github.com/acme/infer",
            language="Python",
            topics=["llm", "inference"],
            stars=5000,
            forks=300,
            stars_delta_7d=420,
        )
        repo2 = GitHubRepository(
            full_name="acme/tiny", html_url="https://github.com/acme/tiny", language="Rust", stars=40
        )
        s.add_all([repo, repo2])
        await s.flush()
        s.add(
            AITool(
                name="InferKit",
                description="Serving toolkit",
                category="framework",
                license="Apache-2.0",
                repository_id=repo.id,
            )
        )
        s.add(AITool(name="PromptLab", description="Prompt testing", category="platform"))
        s.add_all(
            [
                ResearchPaper(
                    arxiv_id="2611.00001",
                    title="Sparse retrieval for long context",
                    authors=["Ada Lovelace", "Alan Turing"],
                    abstract="We study retrieval heads.",
                    primary_category="cs.CL",
                    published_at=NOW - timedelta(days=1),
                ),
                ResearchPaper(
                    arxiv_id="2611.00002",
                    title="Diffusion scheduling",
                    authors=["Grace Hopper"],
                    primary_category="cs.LG",
                    published_at=NOW - timedelta(days=10),
                ),
            ]
        )
        issue = GitHubIssue(
            repository_id=repo.id,
            number=42,
            title="OOM when streaming",
            html_url="https://github.com/acme/infer/issues/42",
            state=IssueState.OPEN,
            labels=["bug", "priority/critical"],
            opened_at=NOW - timedelta(days=1),
            comments=7,
        )
        issue2 = GitHubIssue(
            repository_id=repo.id,
            number=43,
            title="Fix OOM",
            is_pull_request=True,
            html_url="https://github.com/acme/infer/pull/43",
            state=IssueState.CLOSED,
            opened_at=NOW - timedelta(hours=5),
            closed_at=NOW,
        )
        s.add_all([issue, issue2])
        await s.flush()
        s.add_all(
            [
                SoftwareBug(
                    github_issue_id=issue.id,
                    project="acme/infer",
                    kind=BugKind.PERFORMANCE,
                    severity=Severity.CRITICAL,
                    severity_basis="label: priority/critical",
                    status=IssueState.OPEN,
                    affected_versions=["2.1.0"],
                    source_url=issue.html_url,
                ),
                SoftwareBug(
                    project="other/lib",
                    kind=BugKind.REGRESSION,
                    severity=Severity.MEDIUM,
                    severity_basis="vendor changelog",
                    status=IssueState.CLOSED,
                    fixed_in_version="1.2.1",
                    fix_url="https://example.test/fix",
                    source_url="https://example.test/bug",
                    article_id=seeded["a2"],
                ),
            ]
        )
        s.add_all(
            [
                SecurityVulnerability(
                    cve_id="CVE-2099-0001",
                    description="RCE in example parser",
                    cvss_score=9.8,
                    cvss_version="3.1",
                    severity=Severity.CRITICAL,
                    cwe_ids=["CWE-787"],
                    affected_products=[{"vendor": "example", "product": "parser"}],
                    known_exploited=True,
                    kev_date_added=date.today(),
                    patch_available=True,
                    remediation="Upgrade to 2.0.1 (vendor advisory)",
                    references=[{"url": "https://nvd.nist.gov/vuln/detail/CVE-2099-0001"}],
                    published_at=NOW - timedelta(days=1),
                    article_id=seeded["a3"],
                ),
                SecurityVulnerability(
                    cve_id="CVE-2099-0002",
                    description="Info leak in logger",
                    cvss_score=4.3,
                    severity=Severity.MEDIUM,
                    published_at=NOW - timedelta(days=30),
                ),
                SecurityVulnerability(
                    cve_id="CVE-2099-0003",
                    description="Awaiting analysis",
                    severity=Severity.UNKNOWN,
                    published_at=NOW - timedelta(hours=3),
                ),
            ]
        )
        s.add_all([
            Incident(provider="examplecloud", external_id="inc-1", title="Elevated storage errors",
                     status=IncidentStatus.INVESTIGATING, started_at=NOW - timedelta(hours=1),
                     status_page_url="https://status.example.test/inc-1", last_verified_at=NOW - timedelta(minutes=5),
                     updates=[{"at": NOW.isoformat(), "status": "investigating"}]),
            Incident(provider="examplecloud", external_id="inc-2", title="DNS degradation",
                     status=IncidentStatus.IDENTIFIED, started_at=NOW - timedelta(days=2),
                     status_page_url="https://status.example.test/inc-2", last_verified_at=NOW - timedelta(days=1)),
            Incident(provider="otherai", external_id="inc-3", title="API latency", status=IncidentStatus.RESOLVED,
                     started_at=NOW - timedelta(days=3), resolved_at=NOW - timedelta(days=3, hours=-2),
                     status_page_url="https://status.other.test/inc-3", last_verified_at=NOW),
        ])  # fmt: skip
        await s.commit()
        return {"llama": llama.id, "repo": repo.id}


# ------------------------------------------------------------------ shared list semantics
async def test_invalid_sort_lists_allowed_values(client):
    r = await client.get("/api/v1/security/vulnerabilities", params={"sort": "-password"})
    assert r.status_code == 400
    assert r.json()["error"]["message"] == "Invalid sort '-password'"
    assert "-cvss_score" in r.json()["error"]["details"]["allowed"]


async def test_unknown_query_params_are_rejected(client):
    r = await client.get("/api/v1/tools", params={"pagesize": 5})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_bad_date_range_and_page_size(client):
    r = await client.get(
        "/api/v1/research", params={"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}
    )
    assert r.status_code == 422
    assert (await client.get("/api/v1/bugs", params={"page_size": 500})).status_code == 422


async def test_empty_lists(client):
    for path in ("/models", "/tools", "/research", "/github/repositories", "/github/issues", "/bugs",
                 "/security/vulnerabilities", "/incidents", "/models/releases"):  # fmt: skip
        r = await client.get(f"/api/v1{path}")
        assert r.status_code == 200, path
        assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}


# ------------------------------------------------------------------ models
async def test_models_list_and_detail(client, intel):
    body = (await client.get("/api/v1/models", params={"sort": "name"})).json()
    assert [m["name"] for m in body["items"]] == ["Example-7B", "Other-Pro"]
    ex = body["items"][0]
    assert ex["release_count"] == 2 and ex["latest_release"]["version"] == "1.1"

    r = await client.get("/api/v1/models", params={"open_weights": False})
    assert [m["name"] for m in r.json()["items"]] == ["Other-Pro"]
    r = await client.get("/api/v1/models", params={"modality": "vision", "provider": "otherlab"})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/models", params={"q": "7b"})
    assert r.json()["total"] == 1

    d = (await client.get(f"/api/v1/models/{intel['llama']}")).json()
    assert [x["version"] for x in d["releases"]] == ["1.1", "1.0"]
    assert (await client.get(f"/api/v1/models/{uuid.uuid4()}")).status_code == 404


async def test_model_releases(client, intel):
    r = await client.get("/api/v1/models/releases")
    assert [x["version"] for x in r.json()["items"]] == ["1.1", "1.0"]
    assert r.json()["items"][0]["model"]["name"] == "Example-7B"
    since = (NOW - timedelta(days=7)).isoformat()
    r = await client.get("/api/v1/models/releases", params={"date_from": since})
    assert [x["version"] for x in r.json()["items"]] == ["1.1"]


# ------------------------------------------------------------------ tools / research
async def test_tools(client, intel):
    items = (await client.get("/api/v1/tools")).json()["items"]
    assert [t["name"] for t in items] == ["InferKit", "PromptLab"]
    assert items[0]["repository"]["full_name"] == "acme/infer" and items[1]["repository"] is None
    r = await client.get("/api/v1/tools", params={"category": "platform"})
    assert [t["name"] for t in r.json()["items"]] == ["PromptLab"]
    r = await client.get("/api/v1/tools", params={"license": "apache-2.0"})
    assert r.json()["total"] == 1
    assert (await client.get(f"/api/v1/tools/{items[0]['id']}")).json()["name"] == "InferKit"


async def test_research(client, intel):
    r = await client.get("/api/v1/research")
    assert [p["arxiv_id"] for p in r.json()["items"]] == ["2611.00001", "2611.00002"]
    r = await client.get("/api/v1/research", params={"author": "hopper"})
    assert [p["arxiv_id"] for p in r.json()["items"]] == ["2611.00002"]
    r = await client.get("/api/v1/research", params={"q": "retrieval", "primary_category": "cs.CL"})
    assert r.json()["total"] == 1
    assert (await client.get("/api/v1/research/2611.00001")).json()["authors"] == [
        "Ada Lovelace",
        "Alan Turing",
    ]
    assert (await client.get("/api/v1/research/9999.99999")).status_code == 404


async def test_like_wildcards_are_literal(client, intel):
    assert (await client.get("/api/v1/tools", params={"q": "%"})).json()["total"] == 0
    assert (await client.get("/api/v1/tools", params={"q": "_"})).json()["total"] == 0


# ------------------------------------------------------------------ GitHub
async def test_github_repositories(client, intel):
    items = (await client.get("/api/v1/github/repositories")).json()["items"]
    assert [x["full_name"] for x in items] == ["acme/infer", "acme/tiny"]
    r = await client.get("/api/v1/github/repositories", params={"sort": "-stars_delta_7d"})
    assert r.json()["items"][0]["full_name"] == "acme/infer"  # NULL delta sorts last
    r = await client.get("/api/v1/github/repositories", params={"language": "rust"})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/github/repositories", params={"min_stars": 1000, "topic": "llm"})
    assert r.json()["total"] == 1
    d = await client.get("/api/v1/github/repositories/by-name/ACME/infer")
    assert d.status_code == 200 and d.json()["star_history"] == []
    assert (await client.get("/api/v1/github/repositories/by-name/acme/nope")).status_code == 404
    assert (await client.get(f"/api/v1/github/repositories/{intel['repo']}")).status_code == 200


async def test_github_issues(client, intel):
    r = await client.get("/api/v1/github/issues", params={"state": "open"})
    assert [i["number"] for i in r.json()["items"]] == [42]
    assert r.json()["items"][0]["repository"]["full_name"] == "acme/infer"
    r = await client.get("/api/v1/github/issues", params={"is_pull_request": True})
    assert [i["number"] for i in r.json()["items"]] == [43]
    r = await client.get(
        "/api/v1/github/issues", params={"label": "priority/critical", "repository": "acme/infer"}
    )
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/github/issues", params={"sort": "-comments"})
    assert r.json()["items"][0]["number"] == 42


# ------------------------------------------------------------------ bugs
async def test_bugs(client, intel):
    r = await client.get("/api/v1/bugs", params={"sort": "-severity"})
    items = r.json()["items"]
    assert [b["severity"] for b in items] == ["critical", "medium"]
    crit = items[0]
    assert crit["title"] == "OOM when streaming"  # from the linked GitHub issue
    assert crit["issue_number"] == 42 and crit["repository"] == "acme/infer"
    assert crit["severity_basis"] == "label: priority/critical"
    assert "priority/critical" in crit["labels"]
    assert items[1]["title"].startswith("Kubernetes 1.99")  # from the linked article
    r = await client.get("/api/v1/bugs", params={"has_fix": True})
    assert [b["project"] for b in r.json()["items"]] == ["other/lib"]
    r = await client.get("/api/v1/bugs", params={"kind": "performance", "status": "open"})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/bugs", params={"q": "streaming"})
    assert r.json()["total"] == 1
    assert (await client.get(f"/api/v1/bugs/{crit['id']}")).json()["fix_url"] is None


# ------------------------------------------------------------------ security
async def test_vulnerabilities(client, intel):
    r = await client.get("/api/v1/security/vulnerabilities", params={"sort": "-cvss_score"})
    ids = [v["cve_id"] for v in r.json()["items"]]
    assert ids == ["CVE-2099-0001", "CVE-2099-0002", "CVE-2099-0003"]  # no score -> last
    r = await client.get("/api/v1/security/vulnerabilities", params={"known_exploited": True})
    assert [v["cve_id"] for v in r.json()["items"]] == ["CVE-2099-0001"]
    r = await client.get("/api/v1/security/vulnerabilities", params={"min_cvss": 5})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/security/vulnerabilities", params={"product": "parser", "cwe": "CWE-787"})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/security/vulnerabilities", params={"cwe": "787"})
    assert r.status_code == 422
    r = await client.get("/api/v1/security/vulnerabilities", params={"severity": ["critical", "medium"]})
    assert r.json()["total"] == 2
    # mitigation is shown in lists too (official sources only)
    crit = [v for v in r.json()["items"] if v["cve_id"] == "CVE-2099-0001"][0]
    assert crit["remediation"].startswith("Upgrade") and "last_verified_at" in crit


async def test_vulnerability_detail_and_stats(client, intel):
    d = (await client.get("/api/v1/security/vulnerabilities/cve-2099-0001")).json()
    assert d["cve_id"] == "CVE-2099-0001" and d["remediation"].startswith("Upgrade")
    assert d["references"][0]["url"].startswith("https://nvd.nist.gov/")
    r = await client.get("/api/v1/security/vulnerabilities/CVE-2099-9999")
    assert r.status_code == 404 and "has not been collected" in r.json()["error"]["message"]
    r = await client.get("/api/v1/security/vulnerabilities/not-a-cve")
    assert r.status_code == 400
    s = (await client.get("/api/v1/security/stats")).json()
    assert s == {
        "total": 3,
        "by_severity": {"critical": 1, "medium": 1, "unknown": 1},
        "known_exploited": 1,
        "published_last_7d": 2,
        "critical_last_7d": 1,
    }


# ------------------------------------------------------------------ incidents
async def test_incidents_active_requires_fresh_verification(client, intel):
    items = {i["external_id"]: i for i in (await client.get("/api/v1/incidents")).json()["items"]}
    assert items["inc-1"]["is_active"] is True and items["inc-1"]["status_is_stale"] is False
    # unresolved on the status page but last verified a day ago -> not claimed as live
    assert items["inc-2"]["is_active"] is False and items["inc-2"]["status_is_stale"] is True
    assert items["inc-3"]["is_active"] is False and items["inc-3"]["status_is_stale"] is False

    r = await client.get("/api/v1/incidents", params={"active_only": True})
    assert [i["external_id"] for i in r.json()["items"]] == ["inc-1"]
    r = await client.get("/api/v1/incidents", params={"provider": "OTHERAI"})
    assert r.json()["total"] == 1
    r = await client.get("/api/v1/incidents", params={"status": ["resolved", "identified"]})
    assert r.json()["total"] == 2
    d = (await client.get(f"/api/v1/incidents/{items['inc-1']['id']}")).json()
    assert d["updates"][0]["status"] == "investigating"
    assert (await client.get("/api/v1/dashboard/summary")).json()["active_incidents"] == 1


# ------------------------------------------------------------------ search
async def test_search_keyword_with_snippets(client, seeded):
    r = await client.get("/api/v1/search", params={"q": "retrieval generation"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["mode"] == "keyword"
    hit = body["items"][0]
    assert hit["article"]["id"] == str(seeded["a1"])
    assert "[[" in hit["snippet"] and "]]" in hit["snippet"] and hit["rank"] > 0

    r = await client.get("/api/v1/search", params={"q": "release", "item_type": "devops"})
    assert [h["article"]["id"] for h in r.json()["items"]] == [str(seeded["a2"])]


async def test_search_validation_and_unavailable_modes(client, seeded):
    assert (await client.get("/api/v1/search")).status_code == 422
    assert (await client.get("/api/v1/search", params={"q": " a "})).status_code == 422
    r = await client.get("/api/v1/search", params={"q": "rag", "mode": "semantic"})
    assert r.status_code == 501 and r.json()["error"]["code"] == "not_available"
    r = await client.get("/api/v1/search", params={"q": "zzzz-nothing"})
    assert r.json()["items"] == [] and r.json()["pages"] == 0
