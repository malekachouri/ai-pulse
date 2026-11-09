"""Bugs & Failures Radar, vendor advisories, bug enrichment and the alert engine."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.alerts.engine import AlertEngine, AlertSettings
from app.ingestion.connectors.github import affected_versions, fix_from_timeline, resolution_for
from app.models import (
    Article,
    GitHubIssue,
    GitHubRepository,
    Incident,
    Notification,
    SecurityVulnerability,
    SoftwareBug,
    Source,
    User,
    UserPreference,
)
from app.models.enums import (
    BugKind,
    BugResolution,
    IncidentStatus,
    IssueState,
    ItemType,
    Severity,
    SourceType,
)
from app.services.radar import incident_categories
from tests.conftest import PASSWORD, register_and_login
from tests.ingestion_helpers import MockHttp, ingest, js, make_source

NOW = datetime.now(UTC)


# ------------------------------------------------------------------ unit
def test_affected_versions_only_literal_values():
    body = "### Your environment\nvLLM Version: 0.6.3.post1\nPyTorch version: 2.5.1\n### transformers version\n\n4.46.0\nI also tried 1.2"
    assert affected_versions(body) == ["0.6.3.post1", "2.5.1", "4.46.0"]
    assert affected_versions("It crashes since yesterday.") == [] and affected_versions(None) == []


def test_fix_detection_and_resolution():
    pr = {
        "event": "cross-referenced",
        "source": {
            "issue": {
                "html_url": "https://github.com/o/r/pull/9",
                "pull_request": {"merged_at": "2026-11-08T00:00:00Z"},
            }
        },
    }
    unmerged = {
        "event": "cross-referenced",
        "source": {"issue": {"html_url": "x", "pull_request": {"merged_at": None}}},
    }
    commit = {"event": "closed", "commit_id": "abc123", "created_at": "2026-11-08T01:00:00Z"}
    assert fix_from_timeline([unmerged, pr], "o/r")["url"].endswith("/pull/9")
    assert fix_from_timeline([unmerged, commit], "o/r")["url"] == "https://github.com/o/r/commit/abc123"
    assert fix_from_timeline([unmerged], "o/r") is None
    closed = {"state": "closed", "state_reason": "completed"}
    assert resolution_for(closed, {"url": "x"}) == BugResolution.FIXED
    assert resolution_for(closed, None) == BugResolution.COMPLETED  # no linked fix -> not claimed "fixed"
    assert (
        resolution_for({"state": "closed", "state_reason": "not_planned"}, None) == BugResolution.NOT_PLANNED
    )
    assert resolution_for({"state": "open"}, None) is None


@pytest.mark.parametrize(
    ("provider", "title", "services", "expected"),
    [
        ("OpenAI", "Elevated errors for ChatGPT", [], {"ai_provider", "api"}),
        ("Google Cloud", "Cloud SQL instances unavailable", ["Cloud SQL"], {"cloud", "database"}),
        ("Docker", "Docker Hub registry degraded", [], {"kubernetes_docker"}),
        ("GitHub", "Incident with Webhooks", [], {"developer_platform"}),
        ("AWS", "Increased connectivity issues", ["EC2"], {"cloud", "infrastructure"}),
    ],
)
def test_incident_categories(provider, title, services, expected):
    assert expected <= set(incident_categories(provider, title, services))


# ------------------------------------------------------------------ fixtures
@pytest.fixture
async def radar_data(session_factory):
    async with session_factory() as s:
        src = Source(
            slug="r",
            name="R",
            source_type=SourceType.API,
            connector="rss",
            url="https://r.test",
            default_item_type=ItemType.BUG,
            is_official=True,
            reliability=0.9,
        )
        s.add(src)
        await s.flush()
        repo = GitHubRepository(full_name="acme/infer", html_url="https://github.com/acme/infer")
        s.add(repo)
        await s.flush()
        issues = []
        for n, (labels, state) in enumerate(
            [
                (["bug", "priority/critical-urgent"], IssueState.OPEN),
                (["bug"], IssueState.OPEN),
                (["bug"], IssueState.CLOSED),
            ],
            start=1,
        ):
            i = GitHubIssue(
                repository_id=repo.id,
                number=n,
                title=f"Issue {n}",
                html_url=f"https://github.com/acme/infer/issues/{n}",
                state=state,
                labels=labels,
                opened_at=NOW - timedelta(hours=n),
            )
            s.add(i)
            issues.append(i)
        await s.flush()
        s.add_all(
            [
                SoftwareBug(
                    github_issue_id=issues[0].id,
                    project="acme/infer",
                    kind=BugKind.BUG,
                    severity=Severity.CRITICAL,
                    severity_basis="GitHub label: priority/critical-urgent",
                    status=IssueState.OPEN,
                    affected_versions=["2.1.0"],
                    source_url=issues[0].html_url,
                    last_verified_at=NOW,
                ),
                # "critical" without a basis must never be listed as critical
                SoftwareBug(
                    github_issue_id=issues[1].id,
                    project="acme/infer",
                    kind=BugKind.BUG,
                    severity=Severity.CRITICAL,
                    severity_basis=None,
                    status=IssueState.OPEN,
                    source_url=issues[1].html_url,
                ),
                SoftwareBug(
                    github_issue_id=issues[2].id,
                    project="acme/infer",
                    kind=BugKind.REGRESSION,
                    severity=Severity.UNKNOWN,
                    status=IssueState.CLOSED,
                    resolution=BugResolution.FIXED,
                    fix_url="https://github.com/acme/infer/pull/7",
                    fix_merged_at=NOW - timedelta(hours=1),
                    source_url=issues[2].html_url,
                ),
            ]
        )
        crit = Article(
            source_id=src.id,
            external_id="cve1",
            item_type=ItemType.VULNERABILITY,
            title="CVE-2099-1000: RCE in acme-parser",
            url="https://nvd.nist.gov/vuln/detail/CVE-2099-1000",
            collected_at=NOW,
            published_at=NOW,
            content_hash="c" * 64,
            verification_status="official",
            severity=Severity.CRITICAL,
            severity_basis="CVSS v3.1 base score 9.8 (NVD)",
        )
        s.add(crit)
        await s.flush()
        s.add_all(
            [
                SecurityVulnerability(
                    cve_id="CVE-2099-1000",
                    severity=Severity.CRITICAL,
                    cvss_score=9.8,
                    published_at=NOW - timedelta(hours=3),
                    article_id=crit.id,
                    description="RCE in acme-parser",
                    affected_products=[{"vendor": "acme", "product": "acme-parser"}],
                    last_verified_at=NOW,
                ),
                SecurityVulnerability(
                    cve_id="CVE-2099-1001",
                    severity=Severity.MEDIUM,
                    cvss_score=5.0,
                    published_at=NOW - timedelta(hours=5),
                    description="Info leak in kubelet logs",
                    affected_products=[{"vendor": "kubernetes", "product": "kubelet"}],
                ),
                SecurityVulnerability(
                    cve_id="CVE-2015-0001",
                    severity=Severity.UNKNOWN,
                    known_exploited=True,
                    kev_date_added=NOW.date(),
                    kev_due_date=NOW.date() + timedelta(days=21),
                    remediation="CISA required action: apply vendor updates.",
                    affected_products=[{"vendor": "Microsoft", "product": "Windows"}],
                ),
                SecurityVulnerability(
                    cve_id="CVE-2014-0001",
                    severity=Severity.UNKNOWN,
                    known_exploited=True,
                    kev_date_added=date(2021, 11, 3),
                    affected_products=[{"vendor": "Adobe", "product": "Flash Player"}],
                ),
            ]
        )
        s.add_all(
            [
                Incident(
                    provider="OpenAI",
                    external_id="a",
                    title="Elevated API error rates",
                    status=IncidentStatus.INVESTIGATING,
                    impact="major",
                    started_at=NOW - timedelta(hours=1),
                    status_page_url="https://status.openai.com/incidents/a",
                    last_verified_at=NOW - timedelta(minutes=5),
                ),
                Incident(
                    provider="OpenAI",
                    external_id="m",
                    title="Minor latency",
                    status=IncidentStatus.MONITORING,
                    impact="minor",
                    started_at=NOW - timedelta(hours=2),
                    status_page_url="https://status.openai.com/incidents/m",
                    last_verified_at=NOW - timedelta(minutes=5),
                ),
                Incident(
                    provider="AWS",
                    external_id="old",
                    title="Service disruption",
                    status=IncidentStatus.INVESTIGATING,
                    started_at=NOW - timedelta(days=40),
                    status_page_url="https://health.aws.amazon.com/health/status",
                    last_verified_at=NOW - timedelta(days=1),
                ),  # old reading -> never "active"
                Incident(
                    provider="GitHub",
                    external_id="r",
                    title="Incident with Webhooks",
                    status=IncidentStatus.RESOLVED,
                    impact="minor",
                    started_at=NOW - timedelta(days=2, hours=3),
                    resolved_at=NOW - timedelta(days=2),
                    status_page_url="https://www.githubstatus.com/incidents/r",
                    last_verified_at=NOW,
                ),
            ]
        )
        await s.commit()
        return {"repo": repo.id}


# ------------------------------------------------------------------ radar API
async def test_radar_summary(client, radar_data):
    d = (await client.get("/api/v1/radar/summary")).json()
    assert [b["issue_number"] for b in d["critical_bugs"]] == [1]  # the basis-less "critical" bug is excluded
    assert (
        d["critical_bugs"][0]["severity_basis"].startswith("GitHub label")
        and d["critical_bugs"][0]["last_verified_at"]
    )
    assert [v["cve_id"] for v in d["new_vulnerabilities"]] == ["CVE-2099-1000"]
    assert [v["cve_id"] for v in d["newly_exploited"]] == ["CVE-2015-0001"]
    assert {i["external_id"] for i in d["active_incidents"]} == {"a", "m"}
    assert all(i["state"] == "current" for i in d["active_incidents"])
    assert [i["external_id"] for i in d["resolved_incidents"]] == ["r"] and d["resolved_incidents"][0][
        "duration_minutes"
    ] == 180
    assert d["unverified_incidents"] == 1  # the stale AWS reading
    names = {m["name"] for m in d["most_affected"]}
    assert (
        "acme-parser" in names and "windows" in names and "flash player" not in names
    )  # 2021 KEV entry is out of window
    assert len(d["weekly"]) == 8 and d["weekly"][-1]["bugs_fixed"] == 1 and d["weekly"][-1]["kev_added"] == 1
    assert {r["key"] for r in d["severity_chart"]} == {"critical", "medium"}


async def test_incident_state_and_category_filters(client, radar_data):
    r = (await client.get("/api/v1/incidents", params={"state": "current"})).json()
    assert {i["external_id"] for i in r["items"]} == {"a", "m"}
    r = (await client.get("/api/v1/incidents", params={"state": "unverified"})).json()
    assert [i["external_id"] for i in r["items"]] == ["old"] and r["items"][0]["is_active"] is False
    r = (await client.get("/api/v1/incidents", params={"state": "historical"})).json()
    assert [i["external_id"] for i in r["items"]] == ["r"]
    r = (await client.get("/api/v1/incidents", params={"category": "ai_provider"})).json()
    assert {i["external_id"] for i in r["items"]} == {"a", "m"} and "api" in r["items"][0]["categories"]
    assert (await client.get("/api/v1/incidents", params={"category": "nope"})).status_code == 422


async def test_bug_filters_and_fields(client, radar_data):
    fixed = (await client.get("/api/v1/bugs", params={"resolution": "fixed"})).json()["items"]
    assert len(fixed) == 1 and fixed[0]["fix_url"].endswith("/pull/7") and fixed[0]["kind"] == "regression"
    new = (await client.get("/api/v1/bugs", params={"reported_within_days": 1})).json()
    assert new["total"] == 3
    open_crit = (
        await client.get(
            "/api/v1/bugs", params={"status": "open", "severity": "critical", "sort": "-severity"}
        )
    ).json()["items"]
    first = next(b for b in open_crit if b["issue_number"] == 1)
    assert first["affected_versions"] == ["2.1.0"] and first["labels"] == ["bug", "priority/critical-urgent"]


async def test_vulnerability_fields(client, radar_data):
    v = (
        await client.get(
            "/api/v1/security/vulnerabilities", params={"known_exploited": True, "sort": "-kev_date_added"}
        )
    ).json()["items"][0]
    assert v["cve_id"] == "CVE-2015-0001" and v["remediation"].startswith("CISA required action")
    assert v["cvss_score"] is None and v["severity"] == "unknown"  # KEV publishes no score; none invented


# ------------------------------------------------------------------ connectors
async def test_github_issues_enrichment(session_factory):
    base = "https://api.github.com/repos/acme/infer/issues"
    issue = {
        "id": 501,
        "number": 5,
        "title": "Crash",
        "html_url": "https://github.com/acme/infer/issues/5",
        "state": "closed",
        "state_reason": "completed",
        "labels": [{"name": "bug"}, {"name": "performance"}],
        "comments": 1,
        "created_at": "2026-11-08T10:00:00Z",
        "updated_at": "2026-11-08T12:00:00Z",
        "closed_at": "2026-11-08T12:00:00Z",
        "user": {"login": "u"},
        "body": "### Environment\nacme version: 2.4.1\n",
    }
    timeline = [
        {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "html_url": "https://github.com/acme/infer/pull/6",
                    "pull_request": {"merged_at": "2026-11-08T11:59:00Z"},
                }
            },
        }
    ]
    mock = MockHttp({f"{base}/5/timeline": js(timeline), base: js([issue])})
    sid = await make_source(
        session_factory, "github_issues", "https://api.github.com", config={"repos": [{"repo": "acme/infer"}]}
    )
    job = await ingest(session_factory, sid, mock)
    assert job.items_created == 1
    async with session_factory() as s:
        bug = (await s.scalars(select(SoftwareBug))).unique().one()
    assert bug.resolution == BugResolution.FIXED and bug.fix_url.endswith("/pull/6") and bug.fix_merged_at
    assert bug.affected_versions == ["2.4.1"] and bug.kind == BugKind.PERFORMANCE and bug.last_verified_at


async def test_github_advisories_connector(session_factory):
    url = "https://api.github.com/advisories"
    adv = {
        "ghsa_id": "GHSA-aaaa-bbbb-cccc",
        "cve_id": "CVE-2099-2000",
        "html_url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
        "summary": "Path traversal in examplelib",
        "description": "Details.",
        "severity": "high",
        "published_at": "2026-11-08T10:00:00Z",
        "updated_at": "2026-11-09T10:00:00Z",
        "withdrawn_at": None,
        "vulnerabilities": [
            {
                "package": {"ecosystem": "pip", "name": "examplelib"},
                "vulnerable_version_range": "< 1.4.2",
                "first_patched_version": "1.4.2",
            }
        ],
        "cvss_severities": {
            "cvss_v3": {"vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", "score": 7.5}
        },
        "cwes": [{"cwe_id": "CWE-22", "name": "Path Traversal"}],
        "references": ["https://example.test/fix"],
    }
    withdrawn = {
        **adv,
        "ghsa_id": "GHSA-dead-dead-dead",
        "cve_id": "CVE-2099-2001",
        "withdrawn_at": "2026-11-09T00:00:00Z",
    }
    no_cve = {**adv, "ghsa_id": "GHSA-nocv-nocv-nocv", "cve_id": None, "summary": "Prototype pollution"}
    sid = await make_source(session_factory, "github_advisories", url, config={"ecosystems": ["pip"]})
    mock = MockHttp({url: js([adv, withdrawn, no_cve])})
    job = await ingest(session_factory, sid, mock)
    assert job.items_created == 2 and mock.requests[0].url.params["type"] == "reviewed"
    async with session_factory() as s:
        v = await s.scalar(
            select(SecurityVulnerability).where(SecurityVulnerability.cve_id == "CVE-2099-2000")
        )
        assert (
            await s.scalar(select(func.count(SecurityVulnerability.id))) == 1
        )  # withdrawn skipped, GHSA-only = article
        a = await s.scalar(select(Article).where(Article.external_id == "GHSA-aaaa-bbbb-cccc"))
    assert v.cvss_score == 7.5 and v.severity == Severity.HIGH and v.patch_available is True
    assert (
        v.remediation == "GitHub Security Advisory GHSA-aaaa-bbbb-cccc: upgrade examplelib to 1.4.2 or later."
    )
    assert v.affected_products[0]["vulnerable_range"] == "< 1.4.2" and v.cwe_ids == ["CWE-22"]
    assert a.severity_basis == "GitHub Security Advisory severity: high (CVSS 7.5)"
    assert (await ingest(session_factory, sid, MockHttp({url: js([adv])}))).items_fetched == 0  # checkpoint


# ------------------------------------------------------------------ alerts
async def _user(session_factory, email, **prefs):
    async with session_factory() as s:
        u = User(email=email, password_hash="x", role_id=3)
        s.add(u)
        await s.flush()
        s.add(UserPreference(user_id=u.id, **prefs))
        await s.commit()
        return u.id


async def _notes(session_factory, uid):
    async with session_factory() as s:
        return (await s.scalars(select(Notification).where(Notification.user_id == uid))).all()


async def test_alert_rules_defaults_and_idempotency(session_factory, radar_data):
    uid = await _user(session_factory, "a@example.com", followed_repositories=["acme/infer"])
    async with session_factory() as s:
        stats = await AlertEngine(s).run()
        await s.commit()
    titles = sorted(n.title for n in await _notes(session_factory, uid))
    assert any(t.startswith("New critical CVE: CVE-2099-1000 (CVSS 9.8)") for t in titles)
    assert any(t.startswith("Actively exploited: CVE-2015-0001") for t in titles)
    assert any(t.startswith("Critical bug in acme/infer: Issue 1") for t in titles)
    assert any(
        t.startswith("OpenAI incident: Elevated API error rates") for t in titles
    )  # major >= default "major"
    assert not any("Minor latency" in t or "Issue 2" in t or "Service disruption" in t for t in titles)
    assert not any("CVE-2099-1001" in t for t in titles)  # medium, not watched
    async with session_factory() as s:
        again = await AlertEngine(s).run()
        await s.commit()
    assert stats.created == 4 and again.created == 0 and len(await _notes(session_factory, uid)) == 4


async def test_alert_thresholds_and_watched_tech(session_factory, radar_data):
    strict = await _user(
        session_factory,
        "s@example.com",
        alert_settings={
            "min_cvss": 9.9,
            "exploited": False,
            "outage_min_impact": "minor",
            "outage_providers": ["openai"],
            "bug_projects": ["other/repo"],
        },
    )
    watcher = await _user(
        session_factory,
        "w@example.com",
        followed_technologies=["kubelet"],
        min_notification_severity="medium",
        alert_settings={"critical_cves": False, "outages": False},
    )
    async with session_factory() as s:
        await AlertEngine(s).run()
        await s.commit()
    st = sorted(n.title for n in await _notes(session_factory, strict))
    assert not any("CVE-2099-1000" in t for t in st)  # 9.8 < min_cvss 9.9
    assert not any("Actively exploited" in t for t in st) and not any("Critical bug" in t for t in st)
    assert sum("OpenAI incident" in t for t in st) == 2  # minor threshold includes the minor incident
    wt = [n for n in await _notes(session_factory, watcher)]
    assert [n.title for n in wt if "CVE-2099-1001" in n.title] == [
        "New medium CVE: CVE-2099-1001 (CVSS 5.0) — affects kubelet"
    ]
    assert not any("CVE-2099-1000" in n.title for n in wt)  # critical CVE rule switched off, not watched


async def test_no_alert_without_severity_basis(session_factory, radar_data):
    uid = await _user(session_factory, "b@example.com")
    async with session_factory() as s:
        await s.execute(SecurityVulnerability.__table__.update().values(cvss_score=None))
        await s.execute(Article.__table__.update().values(severity_basis=None))
        await AlertEngine(s).run()
        await s.commit()
    assert not any(n.title.startswith("New critical CVE") for n in await _notes(session_factory, uid))


async def test_alert_settings_via_preferences_api(client, radar_data):
    token = await register_and_login(client, "p@example.com")
    h = {"Authorization": f"Bearer {token}"}
    p = (await client.get("/api/v1/preferences", headers=h)).json()
    assert p["alert_settings"] == AlertSettings().model_dump()
    r = await client.put(
        "/api/v1/preferences",
        json={"alert_settings": {"min_cvss": 9, "outage_min_impact": "critical", "critical_bugs": False}},
        headers=h,
    )
    assert (
        r.status_code == 200
        and r.json()["alert_settings"]["min_cvss"] == 9
        and r.json()["alert_settings"]["exploited"]
    )
    bad = await client.put("/api/v1/preferences", json={"alert_settings": {"min_cvss": 11}}, headers=h)
    assert bad.status_code == 422
    bad = await client.put(
        "/api/v1/preferences", json={"alert_settings": {"outage_min_impact": "catastrophic"}}, headers=h
    )
    assert bad.status_code == 422
    assert (
        await client.post("/api/v1/auth/login", json={"email": "p@example.com", "password": PASSWORD})
    ).status_code == 200


def test_incident_terms_match_word_starts_only():
    # regression: "rds" (Amazon RDS) used to match inside "Mastercards"
    cats = incident_categories("OpenAI", "Elevated error rates with some U.S. business Mastercards", [])
    assert "database" not in cats and {"ai_provider", "api"} <= set(cats)
    assert "kubernetes_docker" in incident_categories("X", "Docker Hub containers degraded", [])


async def test_weekly_outage_time_ignores_inconsistent_timestamps(client, session_factory, radar_data):
    async with session_factory() as s:
        s.add(
            Incident(
                provider="Odd",
                external_id="neg",
                title="Clock skew",
                status=IncidentStatus.RESOLVED,
                started_at=NOW - timedelta(hours=1),
                resolved_at=NOW - timedelta(hours=6),
                status_page_url="https://status.odd.test/neg",
                last_verified_at=NOW,
            )
        )
        await s.commit()
    d = (await client.get("/api/v1/radar/summary")).json()
    assert all(w["outage_minutes"] >= 0 for w in d["weekly"])
    r = (await client.get("/api/v1/incidents", params={"category": "database"})).json()
    assert all("Mastercard" not in i["title"] for i in r["items"])
