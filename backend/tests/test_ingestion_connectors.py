"""Connector behaviour against recorded real responses (and small synthetic edge cases)."""

import json
from datetime import timedelta

from sqlalchemy import func, select

from app.models import (
    AIModel,
    AIModelRelease,
    AITool,
    Article,
    GitHubIssue,
    GitHubRepository,
    Incident,
    ResearchPaper,
    SecurityVulnerability,
    SoftwareBug,
    Source,
)
from app.models.enums import IncidentStatus, JobStatus, Severity
from tests.ingestion_helpers import NOW, MockHttp, fixture_bytes, fixture_json, ingest, js, make_source, xml


async def _count(sf, model, *where):
    async with sf() as s:
        return await s.scalar(select(func.count()).select_from(model).where(*where))


async def _all(sf, stmt):
    async with sf() as s:
        return (await s.scalars(stmt)).unique().all()


# --------------------------------------------------------------------------- RSS
async def test_rss_openai_feed_idempotent_with_conditional_get(session_factory):
    url = "https://openai.com/news/rss.xml"
    sid = await make_source(session_factory, "rss", url, config={"categories": ["ai-models"]})
    feed = fixture_bytes("openai_news.xml")
    mock = MockHttp(
        {
            url: [
                xml(feed, headers={"ETag": '"v1"'}),
                xml(feed, headers={"ETag": '"v1"'}),
                xml(b"", status=304),
            ]
        }
    )
    job = await ingest(session_factory, sid, mock)
    assert job.status == JobStatus.SUCCEEDED and job.items_created == 3
    arts = await _all(session_factory, select(Article).order_by(Article.published_at.desc()))
    for a in arts:
        assert a.url.startswith("https://openai.com/") and a.published_at and a.collected_at
        assert a.verification_status == "official" and a.content_hash and a.canonical_key.startswith("url:")
        assert "ai-models" in [c.slug for c in a.categories]

    job2 = await ingest(session_factory, sid, mock)
    assert (job2.items_created, job2.items_skipped) == (0, 3)
    assert mock.requests[1].headers["If-None-Match"] == '"v1"'
    job3 = await ingest(session_factory, sid, mock)  # 304 Not Modified
    assert job3.status == JobStatus.SUCCEEDED and job3.items_fetched == 0
    assert await _count(session_factory, Article) == 3


async def test_rss_detects_content_change(session_factory):
    url = "https://deepmind.google/blog/rss.xml"
    sid = await make_source(session_factory, "rss", url)
    feed = fixture_bytes("deepmind_blog.xml")
    changed = feed.replace(b"Agentic cheminformatics", b"Agentic cheminformatics (updated)")
    mock = MockHttp({url: [xml(feed), xml(changed)]})
    await ingest(session_factory, sid, mock)
    job = await ingest(session_factory, sid, mock)
    assert job.items_updated == 1
    a = (await _all(session_factory, select(Article).where(Article.title.like("%(updated)%"))))[0]
    assert a.source_updated_at is not None


# --------------------------------------------------------------------------- research
async def test_arxiv_papers_and_checkpoint(session_factory):
    url = "https://export.arxiv.org/api/query"
    sid = await make_source(session_factory, "arxiv", url, config={"page_size": 2, "max_pages": 1})
    feed = fixture_bytes("arxiv.xml")
    mock = MockHttp({url: xml(feed)})
    job = await ingest(session_factory, sid, mock)
    assert job.items_created == 2
    papers = await _all(session_factory, select(ResearchPaper))
    assert all(p.authors and p.pdf_url and p.arxiv_id and p.primary_category for p in papers)
    async with session_factory() as s:
        cp = (await s.get(Source, sid)).checkpoint
    assert "last_published" in cp
    job2 = await ingest(session_factory, sid, mock)  # same newest entries -> stops at checkpoint
    assert job2.items_fetched == 0
    assert "sortBy=submittedDate" in str(mock.requests[0].url)


async def test_hf_daily_papers_dedup_with_arxiv(session_factory):
    arxiv_url, hf_url = "https://export.arxiv.org/api/query", "https://huggingface.co/api/daily_papers"
    papers = fixture_json("hf_daily_papers.json")
    arxiv_id = papers[0]["paper"]["id"]
    atom = f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <id>http://arxiv.org/abs/{arxiv_id}v1</id><published>2026-11-04T19:00:06Z</published>
      <title>{papers[0]["paper"]["title"]}</title><summary>s</summary><author><name>A</name></author></entry></feed>"""
    a = await make_source(session_factory, "arxiv", arxiv_url, slug="arxiv")
    h = await make_source(session_factory, "hf_daily_papers", hf_url, slug="hf")
    await ingest(session_factory, a, MockHttp({arxiv_url: xml(atom)}))
    job = await ingest(session_factory, h, MockHttp({hf_url: js(papers)}))
    assert job.items_created == 2
    dup = await _all(session_factory, select(Article).where(Article.duplicate_of_id.is_not(None)))
    assert len(dup) == 1 and dup[0].canonical_key == f"arxiv:{arxiv_id}"
    assert await _count(session_factory, ResearchPaper) == 2  # one row per arXiv id


async def test_hf_models_releases(session_factory):
    url = "https://huggingface.co/api/models"
    sid = await make_source(session_factory, "hf_models", url, config={"authors": {"meta-llama": "Meta"}})
    mock = MockHttp({url: js(fixture_json("hf_models_meta.json"))})
    job = await ingest(session_factory, sid, mock)
    assert job.items_created == 2
    models = await _all(session_factory, select(AIModel))
    assert {m.provider for m in models} == {"Meta"}
    assert await _count(session_factory, AIModelRelease) == 2
    assert "author=meta-llama" in str(mock.requests[0].url)
    assert (await ingest(session_factory, sid, mock)).items_fetched == 0  # checkpoint per org


# --------------------------------------------------------------------------- security
async def test_nvd_prefers_primary_score_and_parses_products(session_factory):
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    sid = await make_source(session_factory, "nvd", url)
    job = await ingest(session_factory, sid, MockHttp({url: js(fixture_json("nvd_page.json"))}))
    assert job.status == JobStatus.SUCCEEDED and job.items_created == 4
    async with session_factory() as s:
        v = await s.scalar(
            select(SecurityVulnerability).where(SecurityVulnerability.cve_id == "CVE-2024-38002")
        )
        art = await s.scalar(select(Article).where(Article.external_id == "CVE-2024-38002"))
    assert v.cvss_score == 8.8 and v.cvss_version == "3.1"  # NVD Primary, not the CNA's CVSS 4.0 9.3
    assert v.severity == Severity.HIGH and art.severity_basis == "CVSS v3.1 base score 8.8 (NVD)"
    assert v.affected_products and v.affected_products[0]["vendor"] == "liferay"
    assert v.references and v.remediation is None  # NVD has no remediation; none invented
    assert "CWE-863" in v.cwe_ids and art.url == "https://nvd.nist.gov/vuln/detail/CVE-2024-38002"


async def test_nvd_paginates_windows_and_skips_rejected(session_factory):
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    page = fixture_json("nvd_page.json")
    v = page["vulnerabilities"]
    rejected = json.loads(json.dumps(v[0]))
    rejected["cve"]["id"], rejected["cve"]["vulnStatus"] = "CVE-2099-0001", "Rejected"

    def handler(request):
        idx = int(request.url.params["startIndex"])
        batch = (
            (v[:2] if idx == 0 else [v[2], rejected])
            if request.url.params["lastModStartDate"].startswith("2026-05")
            else []
        )
        return js({"totalResults": 4 if batch else 0, "vulnerabilities": batch if idx < 4 else []})

    sid = await make_source(session_factory, "nvd", url, config={"page_size": 2},
                            checkpoint={"last_mod_end": "2026-05-01T00:00:00+00:00"})  # fmt: skip
    mock = MockHttp({url: handler})
    job = await ingest(session_factory, sid, mock)
    windows = {r.url.params["lastModStartDate"] for r in mock.requests}
    assert len(windows) == 2  # 192 days -> two windows of <= 120 days
    for r in mock.requests:
        assert r.url.params["lastModEndDate"] <= "2026-11-09T12:00:00.000Z"
    assert job.items_created == 3 and job.items_skipped == 1  # rejected CVE skipped, and counted
    assert (
        await _count(session_factory, SecurityVulnerability, SecurityVulnerability.cve_id == "CVE-2099-0001")
        == 0
    )
    async with session_factory() as s:
        assert (await s.get(Source, sid)).checkpoint["last_mod_end"].startswith("2026-11-09T12:00")


async def test_kev_flags_exploited_and_merges_without_erasing_cvss(session_factory):
    nvd_url, kev_url = "https://services.nvd.nist.gov/rest/json/cves/2.0", "https://www.cisa.gov/kev.json"
    await ingest(session_factory, await make_source(session_factory, "nvd", nvd_url, slug="nvd"),
                 MockHttp({nvd_url: js(fixture_json("nvd_page.json"))}))  # fmt: skip
    kev = fixture_json("cisa_kev.json")
    kev["vulnerabilities"][0]["cveID"] = "CVE-2024-38002"  # overlap with the NVD record
    sid = await make_source(
        session_factory, "cisa_kev", kev_url, slug="kev", config={"article_window_days": 30}
    )
    job = await ingest(session_factory, sid, MockHttp({kev_url: js(kev)}))
    assert job.status == JobStatus.SUCCEEDED
    async with session_factory() as s:
        v = await s.scalar(
            select(SecurityVulnerability).where(SecurityVulnerability.cve_id == "CVE-2024-38002")
        )
        kev_art = await s.scalar(
            select(Article).where(Article.external_id == "CVE-2024-38002", Article.source_id == sid)
        )
    assert v.known_exploited and v.kev_due_date and v.remediation.startswith("CISA required action:")
    assert v.cvss_score == 8.8 and v.severity == Severity.HIGH  # KEV has no CVSS: NVD's facts kept
    assert kev_art.duplicate_of_id is not None  # same CVE already shown from NVD
    assert kev_art.severity is None  # never invented


async def test_kev_old_entries_create_records_without_articles(session_factory):
    url = "https://www.cisa.gov/kev.json"
    kev = fixture_json("cisa_kev.json")
    sid = await make_source(session_factory, "cisa_kev", url, config={"article_window_days": 1})
    job = await ingest(session_factory, sid, MockHttp({url: js(kev)}), now=NOW + timedelta(days=400))
    # New typed-only rows are "created" (they used to be miscounted as "updated").
    assert (job.items_created, job.items_updated, job.items_skipped) == (3, 0, 0)
    assert await _count(session_factory, Article) == 0
    job2 = await ingest(session_factory, sid, MockHttp({url: js(kev)}), now=NOW + timedelta(days=400))
    assert (job2.items_created, job2.items_updated, job2.items_skipped) == (0, 0, 3)
    assert (
        await _count(session_factory, SecurityVulnerability, SecurityVulnerability.known_exploited.is_(True))
        == 3
    )


async def test_kubernetes_cve_feed_cvss_from_src_text(session_factory):
    url = "https://kubernetes.io/cve.json"
    sid = await make_source(session_factory, "kubernetes_cve_feed", url)
    await ingest(session_factory, sid, MockHttp({url: js(fixture_json("kubernetes_cve_feed.json"))}))
    item = fixture_json("kubernetes_cve_feed.json")["items"][0]
    async with session_factory() as s:
        v = await s.scalar(select(SecurityVulnerability).where(SecurityVulnerability.cve_id == item["id"]))
        a = await s.scalar(select(Article).where(Article.external_id == item["id"]))
    assert v.cvss_score == 2.7 and v.severity == Severity.LOW and v.cvss_vector.startswith("CVSS:3.1/")
    assert v.patch_available is True  # feed status "fixed"
    assert a.severity_basis == "Kubernetes SRC CVSS v3.1 2.7" and a.url == item["url"]
    assert {"kubernetes", "cybersecurity"} <= {c.slug for c in a.categories}


# --------------------------------------------------------------------------- status pages
async def test_statuspage_incidents(session_factory):
    url = "https://status.openai.com/api/v2/incidents.json"
    data = fixture_json("statuspage_openai.json")
    ongoing = json.loads(json.dumps(data["incidents"][0]))
    ongoing.update(
        id="ongoing-1", status="identified", impact="major", resolved_at=None, name="Elevated latency"
    )
    data["incidents"].append(ongoing)
    sid = await make_source(session_factory, "statuspage", url, config={"provider": "OpenAI"})
    await ingest(session_factory, sid, MockHttp({url: js(data)}))
    incs = {i.external_id: i for i in await _all(session_factory, select(Incident))}
    assert incs["ongoing-1"].status == IncidentStatus.IDENTIFIED and incs["ongoing-1"].impact == "major"
    assert incs["ongoing-1"].status_page_url == "https://status.openai.com/incidents/ongoing-1"
    expected = {"resolved": IncidentStatus.RESOLVED, "postmortem": IncidentStatus.RESOLVED,
                "monitoring": IncidentStatus.MONITORING, "identified": IncidentStatus.IDENTIFIED,
                "investigating": IncidentStatus.INVESTIGATING}  # fmt: skip
    for raw in fixture_json("statuspage_openai.json")["incidents"]:
        assert incs[raw["id"]].status == expected[raw["status"]]  # provider's own status, mapped 1:1
    async with session_factory() as s:
        a = await s.scalar(select(Article).where(Article.external_id == "ongoing-1"))
    assert a.severity == Severity.HIGH and a.severity_basis == "OpenAI status page impact: major"


async def test_gcp_status_mapping(session_factory):
    url = "https://status.cloud.google.com/incidents.json"
    data = fixture_json("gcp_incidents.json")
    open_one = json.loads(json.dumps(data[0]))
    open_one.update(id="open-1", end=None)
    sid = await make_source(session_factory, "gcp_status", url)
    await ingest(session_factory, sid, MockHttp({url: js([*data, open_one])}))
    incs = {i.external_id: i for i in await _all(session_factory, select(Incident))}
    assert incs["open-1"].status == IncidentStatus.INVESTIGATING
    assert incs[data[0]["id"]].status == IncidentStatus.RESOLVED and incs[data[0]["id"]].resolved_at
    assert incs[data[0]["id"]].status_page_url.startswith("https://status.cloud.google.com/incidents/")
    assert incs[data[0]["id"]].affected_services


async def test_aws_rss_never_marks_old_events_active(session_factory):
    url = "https://status.aws.amazon.com/rss/all.rss"
    real = fixture_bytes("aws_status.rss").decode()
    recent = """<item><title><![CDATA[Service disruption: Increased API Error Rates]]></title>
      <link>https://status.aws.amazon.com/</link><pubDate>Mon, 09 Nov 2026 03:00:00 PST</pubDate>
      <guid isPermaLink="false">https://status.aws.amazon.com/#ec2-us-east-1_1794000000</guid>
      <description><![CDATA[We are investigating.]]></description></item>
      <item><title><![CDATA[Service is operating normally: [RESOLVED] Elevated latency]]></title>
      <link>https://status.aws.amazon.com/</link><pubDate>Mon, 09 Nov 2026 02:00:00 PST</pubDate>
      <guid isPermaLink="false">https://status.aws.amazon.com/#s3-eu-west-1_1793990000</guid></item>"""
    feed = real.replace("</channel>", recent + "</channel>")
    sid = await make_source(session_factory, "aws_status_rss", url)
    await ingest(session_factory, sid, MockHttp({url: xml(feed)}))
    incs = {i.external_id: i for i in await _all(session_factory, select(Incident))}
    old = [i for k, i in incs.items() if "me-central-1" in k or "me-south-1" in k]
    assert old and all(i.status == IncidentStatus.UNKNOWN for i in old)  # September events: not "active"
    assert incs["ec2-us-east-1_1794000000"].status == IncidentStatus.INVESTIGATING
    assert incs["ec2-us-east-1_1794000000"].regions == ["us-east-1"]
    assert incs["s3-eu-west-1_1793990000"].status == IncidentStatus.RESOLVED


async def test_azure_feed_reconciles_removed_items(session_factory):
    url = "https://azure.status.microsoft/en-us/status/feed/"
    item = """<rss version="2.0"><channel><title>Azure Status</title><item><title>Storage - West Europe - Degraded</title>
      <link>https://azure.status.microsoft/en-us/status/</link><guid>az-1</guid>
      <pubDate>Mon, 09 Nov 2026 10:00:00 Z</pubDate><description>Investigating</description></item></channel></rss>"""
    empty = '<rss version="2.0"><channel><title>Azure Status</title></channel></rss>'
    sid = await make_source(session_factory, "azure_status_rss", url)
    mock = MockHttp({url: [xml(item), xml(empty)]})
    await ingest(session_factory, sid, mock)
    assert (await _all(session_factory, select(Incident)))[0].status == IncidentStatus.INVESTIGATING
    await ingest(session_factory, sid, mock)
    inc = (await _all(session_factory, select(Incident)))[0]
    assert inc.status == IncidentStatus.UNKNOWN  # disappeared from the feed; resolution not claimed
    assert inc.resolved_at is None and inc.updates[-1]["status"] == "no longer listed"


# --------------------------------------------------------------------------- GitHub
def _release(id_, tag, published, **kw):
    return {"id": id_, "tag_name": tag, "name": kw.get("name", tag), "html_url": f"https://github.com/o/r/releases/tag/{tag}",
            "published_at": published, "draft": kw.get("draft", False), "prerelease": kw.get("prerelease", False),
            "body": "Changelog", "author": {"login": "bot"}}  # fmt: skip


async def test_github_releases_tools_checkpoints_and_partial_failure(session_factory):
    api = "https://api.github.com/repos/"
    sid = await make_source(
        session_factory, "github_releases", "https://api.github.com",
        config={"repos": [{"repo": "vllm-project/vllm", "kind": "tool", "tool_name": "vLLM"},
                          {"repo": "gone/missing"}]},
    )  # fmt: skip
    releases = [_release(3, "v0.9.0", "2026-11-08T10:00:00Z"), _release(2, "v0.9.0rc1", "2026-11-01T10:00:00Z", prerelease=True),
                _release(1, "v0.8.5", "2026-10-20T10:00:00Z"), _release(4, "v1.0-draft", None, draft=True)]  # fmt: skip
    mock = MockHttp(
        {
            f"{api}vllm-project/vllm/releases": js(releases),
            f"{api}gone/missing": js({"message": "Not Found"}, 404),
        }
    )
    job = await ingest(session_factory, sid, mock)
    assert job.status == JobStatus.PARTIAL and job.items_created == 2  # missing repo logged, others saved
    assert (await _all(session_factory, select(Source)))[0].consecutive_failures == 0
    assert job.errors[0]["ref"] == "gone/missing"
    tool = (await _all(session_factory, select(AITool)))[0]
    assert tool.name == "vLLM" and tool.latest_version == "v0.9.0"
    repo = (
        await _all(
            session_factory, select(GitHubRepository).where(GitHubRepository.full_name == "vllm-project/vllm")
        )
    )[0]
    assert repo.latest_release == "v0.9.0"
    job2 = await ingest(session_factory, sid, mock)
    assert job2.items_fetched == 0  # per-repo checkpoint


async def test_github_issues_bugs_severity_and_pagination(session_factory):
    base = "https://api.github.com/repos/acme/infer/issues"

    def issue(n, labels, **kw):
        return {"id": 1000 + n, "number": n, "title": f"Issue {n}", "html_url": f"https://github.com/acme/infer/issues/{n}",
                "state": kw.get("state", "open"), "labels": [{"name": label} for label in labels], "comments": 2,
                "created_at": "2026-11-08T10:00:00Z", "updated_at": f"2026-11-08T1{n}:00:00Z",
                "closed_at": kw.get("closed_at"), "user": {"login": "u"}, "body": "steps", **kw.get("extra", {})}  # fmt: skip

    page1 = [issue(1, ["bug", "priority/critical-urgent"]), issue(2, ["question"]),
             issue(3, ["bug"], extra={"pull_request": {}})]  # fmt: skip
    page2 = [
        issue(4, ["kind/regression", "triage/accepted"], state="closed", closed_at="2026-11-08T15:00:00Z")
    ]

    def handler(request):
        if request.url.params.get("page") == "2":
            return js(page2)
        return js(page1, headers={"Link": f'<{base}?page=2>; rel="next"'})

    sid = await make_source(
        session_factory, "github_issues", "https://api.github.com", config={"repos": [{"repo": "acme/infer"}]}
    )
    mock = MockHttp({base: handler})
    job = await ingest(session_factory, sid, mock)
    assert job.items_created == 2 and len(mock.requests) == 2  # question + PR filtered out
    bugs = {b.github_issue.number: b for b in await _all(session_factory, select(SoftwareBug))}
    assert (
        bugs[1].severity == Severity.CRITICAL
        and bugs[1].severity_basis == "GitHub label: priority/critical-urgent"
    )
    assert bugs[4].severity == Severity.UNKNOWN and bugs[4].severity_basis is None  # no documented basis
    assert bugs[4].kind == "regression" and bugs[4].status == "closed"
    async with session_factory() as s:
        a4 = await s.scalar(select(Article).where(Article.external_id == "1004"))
        a1 = await s.scalar(select(Article).where(Article.external_id == "1001"))
        cp = (await s.get(Source, sid)).checkpoint
    assert a4.verification_status == "verified" and a1.verification_status == "unverified"
    assert a4.severity is None and cp["acme/infer"] == "2026-11-08T14:00:00Z"
    assert await _count(session_factory, GitHubIssue) == 2


async def test_github_trending_star_snapshots(session_factory):
    url = "https://api.github.com/search/repositories"

    def repo(stars):
        return {"items": [{"id": 1, "full_name": "acme/rising", "html_url": "https://github.com/acme/rising",
                           "description": "Agents", "language": "Python", "topics": ["llm"], "stargazers_count": stars,
                           "forks_count": 3, "open_issues_count": 1, "pushed_at": "2026-11-08T00:00:00Z",
                           "created_at": "2026-10-01T00:00:00Z"}]}  # fmt: skip

    sid = await make_source(
        session_factory, "github_trending", "https://api.github.com", config={"queries": ["topic:llm"]}
    )
    await ingest(session_factory, sid, MockHttp({url: js(repo(1000))}))
    r = (await _all(session_factory, select(GitHubRepository)))[0]
    assert r.stars_delta_7d is None  # not enough history yet: no number invented
    mock = MockHttp({url: js(repo(1450))})
    job = await ingest(session_factory, sid, mock, now=NOW + timedelta(days=8))
    assert job.items_skipped == 1  # star count change is not a content change
    r = (await _all(session_factory, select(GitHubRepository)))[0]
    assert r.stars == 1450 and r.stars_delta_7d == 450 and len(r.star_history) == 2
    q = mock.requests[0].url.params["q"]
    assert "topic:llm" in q and "stars:>=200" in q and "pushed:>=" in q


async def test_github_every_repo_failing_fails_the_job(session_factory):
    """A multi-repo connector that catches every fetch error must not look healthy."""
    api = "https://api.github.com/repos/"
    sid = await make_source(session_factory, "github_releases", "https://api.github.com",
                            config={"repos": [{"repo": "a/one"}, {"repo": "b/two"}]})  # fmt: skip
    mock = MockHttp({f"{api}a/one/releases": js({"message": "Forbidden"}, 403),
                     f"{api}b/two/releases": js({"message": "Forbidden"}, 403)})  # fmt: skip
    job = await ingest(session_factory, sid, mock)
    assert job.status == JobStatus.FAILED and job.error.startswith("all 2 fetch(es) failed")
    source = (await _all(session_factory, select(Source)))[0]
    assert source.consecutive_failures == 1 and source.last_success_at is None and source.last_error
