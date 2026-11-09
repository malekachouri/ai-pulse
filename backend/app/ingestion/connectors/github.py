"""GitHub REST API connectors.

GitHub has **no trending API**. `github_trending` is a documented alternative: the Search API ranks
repositories matching a query (topic, minimum stars, pushed recently) by stars, and AI Pulse records a daily
star snapshot per repository so "stars gained in 7 days" is computed from our own history.

Authentication: set GITHUB_TOKEN to raise limits (unauthenticated: 60 core requests/hour, 10 searches/minute).
"""

import re
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.base import Connector, ConnectorConfig, FetchResult
from app.ingestion.http import RateLimit
from app.ingestion.normalized import (
    BugPayload,
    IssuePayload,
    NormalizedItem,
    RepositoryPayload,
    ToolPayload,
)
from app.ingestion.text import parse_dt, truncate
from app.models.enums import BugKind, BugResolution, IssueState, ItemType, Severity, VerificationStatus

API = "https://api.github.com"
NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')
REPO_RE = r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"


class _GitHub(Connector):
    def headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.settings.github_token:
            h["Authorization"] = f"Bearer {self.settings.github_token.get_secret_value()}"
        return h

    async def get_json(
        self, url: str, params: dict[str, Any] | None = None, rate: RateLimit | None = None
    ) -> tuple[Any, str | None]:
        resp = await self.http.get(
            url, params=params, headers=self.headers(), rate_limit=rate or self.rate_limit
        )
        m = NEXT_RE.search(resp.headers.get("Link", ""))
        return resp.json(), (m.group(1) if m else None)


def _repo_payload(r: dict[str, Any]) -> RepositoryPayload:
    return RepositoryPayload(
        full_name=r["full_name"],
        html_url=r["html_url"],
        github_id=r.get("id"),
        description=r.get("description"),
        language=r.get("language"),
        topics=r.get("topics"),
        stars=r.get("stargazers_count"),
        forks=r.get("forks_count"),
        open_issues=r.get("open_issues_count"),
        pushed_at=parse_dt(r.get("pushed_at")),
    )


# ---------------------------------------------------------------------------- releases
class ReleaseRepo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str = Field(pattern=REPO_RE)
    kind: str = Field("devops", pattern="^(devops|tool|news)$")
    tool_name: str | None = None
    categories: list[str] = Field(default_factory=list)


class GitHubReleasesConfig(ConnectorConfig):
    repos: list[ReleaseRepo] = Field(min_length=1, max_length=100)
    per_repo: int = Field(10, ge=1, le=100)
    include_prereleases: bool = False


class GitHubReleasesConnector(_GitHub):
    key = "github_releases"
    description = "Releases of selected GitHub repositories (Kubernetes, Docker, CNCF, AI frameworks)"
    Config = GitHubReleasesConfig
    config: GitHubReleasesConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        records: list[Any] = []
        cp = dict(checkpoint)
        for rr in self.config.repos:
            try:
                releases, _ = await self.get_json(
                    f"{API}/repos/{rr.repo}/releases", {"per_page": self.config.per_repo}
                )
            except Exception as exc:  # noqa: BLE001 - one missing repo must not block the others
                self.record_error("fetch", f"{type(exc).__name__}: {exc}", ref=rr.repo)
                continue
            since = parse_dt(cp.get(rr.repo))
            for rel in releases:
                published = parse_dt(rel.get("published_at"))
                if rel.get("draft") or (rel.get("prerelease") and not self.config.include_prereleases):
                    continue
                if since and published and published <= since:
                    continue
                records.append((rel, rr))
            dates = [d for d in (parse_dt(r.get("published_at")) for r in releases) if d]
            if dates:
                cp[rr.repo] = max([*dates, since] if since else dates).isoformat()
        # Oldest first, so per-tool "latest version" ends on the newest release.
        records.sort(key=lambda r: r[0].get("published_at") or "")
        return FetchResult(records, checkpoint=cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        rel, rr = record
        tag = rel.get("tag_name") or ""
        name = (rel.get("name") or "").strip()
        title = f"{rr.repo} {tag}" + (f": {name}" if name and name != tag else "")
        body = rel.get("body") or None
        published = parse_dt(rel.get("published_at"))
        item_type = {"devops": ItemType.DEVOPS, "tool": ItemType.TOOL, "news": ItemType.NEWS}[rr.kind]
        item = NormalizedItem(
            external_id=str(rel["id"]),
            item_type=item_type,
            title=title,
            url=rel["html_url"],
            description=truncate(body, 1500),
            content=body,
            author=(rel.get("author") or {}).get("login"),
            published_at=published,
            categories=rr.categories,
            tags=["release", *(["prerelease"] if rel.get("prerelease") else [])],
            verification=self.config.verification,
            canonical_key=f"gh-release:{rr.repo.lower()}:{tag}",
            repository=RepositoryPayload(
                full_name=rr.repo,
                html_url=f"https://github.com/{rr.repo}",
                latest_release=tag,
                latest_release_at=published,
            ),
        )
        if rr.kind == "tool":
            item.tool = ToolPayload(
                name=rr.tool_name or rr.repo.split("/")[1], repository=rr.repo, latest_version=tag
            )
        return [item]


# ---------------------------------------------------------------------------- trending alternative
class GitHubTrendingConfig(ConnectorConfig):
    queries: list[str] = Field(min_length=1, max_length=20, description='Search qualifiers, e.g. "topic:llm"')
    min_stars: int = Field(200, ge=0)
    pushed_within_days: int = Field(30, ge=1, le=365)
    per_query: int = Field(30, ge=1, le=100)


class GitHubTrendingConnector(_GitHub):
    key = "github_trending"
    description = "Rising repositories via Search API + AI Pulse star snapshots (GitHub has no trending API)"
    Config = GitHubTrendingConfig
    config: GitHubTrendingConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        since = (self.now - timedelta(days=self.config.pushed_within_days)).date().isoformat()
        search_rate = self.rate_limit or RateLimit(9, 60)  # search API: 10/min unauthenticated
        seen: dict[str, Any] = {}
        for q in self.config.queries:
            query = f"{q} stars:>={self.config.min_stars} pushed:>={since} archived:false"
            data, _ = await self.get_json(
                f"{API}/search/repositories",
                {"q": query, "sort": "stars", "order": "desc", "per_page": self.config.per_query},
                rate=search_rate,
            )
            for r in data.get("items", []):
                seen.setdefault(r["full_name"], (r, q))
        return FetchResult(list(seen.values()))

    def normalize(self, record: Any) -> list[NormalizedItem]:
        r, query = record
        desc = r.get("description")
        return [
            NormalizedItem(
                external_id=r["full_name"],
                item_type=ItemType.GITHUB_REPO,
                title=f"{r['full_name']}" + (f": {truncate(desc, 200)}" if desc else ""),
                url=r["html_url"],
                description=desc,
                published_at=parse_dt(r.get("created_at")),
                tags=(r.get("topics") or [])[:15],
                verification=VerificationStatus.OFFICIAL,
                canonical_key=f"gh-repo:{r['full_name'].lower()}",
                raw={"matched_query": query},
                repository=_repo_payload(r),
            )
        ]


# ---------------------------------------------------------------------------- issues / bugs
SEVERITY_LABELS: list[tuple[re.Pattern[str], Severity]] = [
    (
        re.compile(
            r"(critical|\bp0\b|priority/critical-urgent|sev(erity)?[ :/-]?(1|critical)|blocker)", re.I
        ),
        Severity.CRITICAL,
    ),
    (
        re.compile(r"(\bp1\b|priority/important-soon|sev(erity)?[ :/-]?(2|high)|priority: ?high)", re.I),
        Severity.HIGH,
    ),
    (
        re.compile(
            r"(\bp2\b|priority/important-longterm|sev(erity)?[ :/-]?(3|medium)|priority: ?medium)", re.I
        ),
        Severity.MEDIUM,
    ),
    (re.compile(r"(\bp3\b|priority/backlog|sev(erity)?[ :/-]?(4|low)|priority: ?low)", re.I), Severity.LOW),
]
KIND_LABELS: list[tuple[re.Pattern[str], BugKind]] = [
    (re.compile(r"security|vulnerab|cve", re.I), BugKind.SECURITY),
    (re.compile(r"regression", re.I), BugKind.REGRESSION),
    (re.compile(r"perf|performance|memory|slow", re.I), BugKind.PERFORMANCE),
    (re.compile(r"compat", re.I), BugKind.COMPATIBILITY),
]
BUG_LABEL = re.compile(
    r"(^|[/: ])(bug|kind/bug|type: ?bug|regression|crash|security|kind/regression|kind/failing-test)", re.I
)
CONFIRMED = re.compile(r"(triage/accepted|confirmed|verified|reproduced)", re.I)


def severity_from_labels(labels: list[str]) -> tuple[Severity, str | None]:
    for pattern, sev in SEVERITY_LABELS:
        for label in labels:
            if pattern.search(label):
                return sev, f"GitHub label: {label}"
    return Severity.UNKNOWN, None


def kind_from_labels(labels: list[str]) -> BugKind:
    for pattern, kind in KIND_LABELS:
        if any(pattern.search(label) for label in labels):
            return kind
    return BugKind.BUG


class IssueRepo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str = Field(pattern=REPO_RE)
    labels: str | None = Field(None, description="Server-side label filter (comma = AND), e.g. 'kind/bug'")
    categories: list[str] = Field(default_factory=list)


class GitHubIssuesConfig(ConnectorConfig):
    repos: list[IssueRepo] = Field(min_length=1, max_length=50)
    verification: VerificationStatus = (
        VerificationStatus.UNVERIFIED
    )  # user reports until a maintainer confirms
    initial_days: int = Field(7, ge=1, le=90)
    max_pages: int = Field(3, ge=1, le=20)
    fix_lookups: int = Field(
        15, ge=0, le=100, description="Closed bugs per run whose timeline is read to find the merged fix"
    )


# "vLLM Version: 0.6.3", "### Transformers version\n\n4.46.0", "Kubernetes version: v1.31.2"
VERSION_LINE = re.compile(
    r"(?im)^[#*\s>-]*[\w .()/-]{0,40}\bversions?\b[^\n:]{0,20}[:\n]+\s*"
    r"`*v?(\d+\.\d+(?:\.\d+)?(?:[-+.][\w.]+)?)`*"
)


def affected_versions(body: str | None, limit: int = 5) -> list[str]:
    """Versions the reporter wrote next to a 'version' label. Only literal values; nothing inferred."""
    if not body:
        return []
    return list(dict.fromkeys(VERSION_LINE.findall(body)))[:limit]


def resolution_for(issue: dict[str, Any], fix: dict[str, Any] | None) -> BugResolution | None:
    if issue.get("state") != "closed":
        return None
    reason = issue.get("state_reason")
    if reason == "not_planned":
        return BugResolution.NOT_PLANNED
    if reason == "duplicate":
        return BugResolution.DUPLICATE
    if fix:
        return BugResolution.FIXED
    return BugResolution.COMPLETED if reason == "completed" else BugResolution.UNKNOWN


def fix_from_timeline(events: list[dict[str, Any]], repo: str) -> dict[str, Any] | None:
    """A merged pull request that references the issue, else the commit that closed it."""
    for e in events:
        src = (e.get("source") or {}).get("issue") or {}
        pr = src.get("pull_request") or {}
        if e.get("event") == "cross-referenced" and pr.get("merged_at"):
            return {"url": src.get("html_url"), "merged_at": pr.get("merged_at"), "kind": "pull_request"}
    for e in events:
        if e.get("event") == "closed" and e.get("commit_id"):
            return {
                "url": f"https://github.com/{repo}/commit/{e['commit_id']}",
                "merged_at": e.get("created_at"),
                "kind": "commit",
            }
    return None


class GitHubIssuesConnector(_GitHub):
    key = "github_issues"
    description = "Bug, regression and security issues (open and closed) of selected repositories"
    Config = GitHubIssuesConfig
    config: GitHubIssuesConfig

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        records: list[Any] = []
        cp = dict(checkpoint)
        for ir in self.config.repos:
            since = cp.get(ir.repo) or (self.now - timedelta(days=self.config.initial_days)).isoformat()
            params: dict[str, Any] | None = {
                "state": "all",
                "since": since,
                "sort": "updated",
                "direction": "asc",
                "per_page": 100,
                **({"labels": ir.labels} if ir.labels else {}),
            }
            url: str | None = f"{API}/repos/{ir.repo}/issues"
            latest = since
            try:
                for _ in range(self.config.max_pages):
                    if not url:
                        break
                    issues, url = await self.get_json(url, params)
                    params = None  # the `next` link already carries the query
                    for issue in issues:
                        latest = max(latest, issue.get("updated_at") or latest)
                        if "pull_request" in issue:
                            continue
                        labels = [label["name"] for label in issue.get("labels", [])]
                        if ir.labels or any(BUG_LABEL.search(label) for label in labels):
                            records.append((issue, ir, labels))
            except Exception as exc:  # noqa: BLE001
                self.record_error("fetch", f"{type(exc).__name__}: {exc}", ref=ir.repo)
                continue
            cp[ir.repo] = latest
        # Linked fixes for closed-as-completed bugs (bounded per run; failures don't block the batch).
        budget = self.config.fix_lookups
        enriched = []
        for issue, ir, labels in records:
            fix = None
            if budget > 0 and issue.get("state") == "closed" and issue.get("state_reason") == "completed":
                budget -= 1
                try:
                    events, _ = await self.get_json(
                        f"{API}/repos/{ir.repo}/issues/{issue['number']}/timeline", {"per_page": 100}
                    )
                    fix = fix_from_timeline(events if isinstance(events, list) else [], ir.repo)
                except Exception as exc:  # noqa: BLE001
                    self.record_error(
                        "fetch", f"timeline: {type(exc).__name__}: {exc}", ref=f"{ir.repo}#{issue['number']}"
                    )
            enriched.append((issue, ir, labels, fix))
        return FetchResult(enriched, checkpoint=cp)

    def normalize(self, record: Any) -> list[NormalizedItem]:
        issue, ir, labels, fix = record
        sev, basis = severity_from_labels(labels)
        state = IssueState.CLOSED if issue.get("state") == "closed" else IssueState.OPEN
        verified = any(CONFIRMED.search(label) for label in labels)
        body = issue.get("body")
        opened = parse_dt(issue["created_at"])
        assert opened is not None
        return [
            NormalizedItem(
                external_id=str(issue["id"]),
                item_type=ItemType.BUG,
                title=f"{ir.repo}#{issue['number']}: {issue['title']}",
                url=issue["html_url"],
                description=truncate(body, 1500),
                content=body,
                author=(issue.get("user") or {}).get("login"),
                published_at=opened,
                source_updated_at=parse_dt(issue.get("updated_at")),
                severity=sev if basis else None,
                severity_basis=basis,
                tags=[label.lower()[:64] for label in labels][:15],
                categories=["bugs", *ir.categories],
                verification=VerificationStatus.VERIFIED if verified else self.config.verification,
                canonical_key=f"gh-issue:{ir.repo.lower()}#{issue['number']}",
                raw={"state_reason": issue.get("state_reason")},
                issue=IssuePayload(
                    repository=ir.repo,
                    number=issue["number"],
                    title=issue["title"],
                    html_url=issue["html_url"],
                    state=state,
                    labels=labels,
                    comments=issue.get("comments", 0),
                    opened_at=opened,
                    source_updated_at=parse_dt(issue.get("updated_at")),
                    closed_at=parse_dt(issue.get("closed_at")),
                ),
                bug=BugPayload(
                    project=ir.repo,
                    kind=kind_from_labels(labels),
                    severity=sev,
                    severity_basis=basis,
                    status=state,
                    resolution=resolution_for(issue, fix),
                    affected_versions=affected_versions(body),
                    fix_url=fix["url"] if fix else None,
                    fix_merged_at=parse_dt(fix["merged_at"]) if fix else None,
                    source_url=issue["html_url"],
                ),
            )
        ]
