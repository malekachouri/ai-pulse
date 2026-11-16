"""Skills radar connectors. They store entries in `ai_skills`, not articles: the MCP Registry alone publishes
thousands of servers a week, which would bury the news feed and the AI analysis queue.

* `mcp_registry` - the official MCP Registry API (registry.modelcontextprotocol.io), latest version of each
  server published or updated since the last run, cursor-paginated and resumable.
* `claude_marketplace` - Claude Code plugin marketplaces (`.claude-plugin/marketplace.json` in a GitHub repo):
  one entry per plugin, plus one per Agent Skill a plugin lists (its SKILL.md front matter).
"""

import hashlib
import posixpath
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.base import Connector, ConnectorConfig, FetchResult, RunResult
from app.ingestion.http import FetchError
from app.ingestion.normalized import NormalizedItem
from app.ingestion.text import parse_dt
from app.models.enums import SkillKind
from app.skills import frontmatter, install
from app.skills.store import SkillRecord, mark_removed, upsert


class _SkillConnector(Connector):
    """Fetch -> records -> upsert into ai_skills. The records are SkillRecord: article stages do not apply."""

    def normalize(self, record: Any) -> list[NormalizedItem]:
        return []  # not articles

    async def reconcile_listing(self, session: AsyncSession, records: list[SkillRecord]) -> None:  # noqa: B027
        """Optional: mark entries that left a full listing."""

    async def run(self, session: AsyncSession, now: datetime) -> RunResult:
        self.now = now
        result = RunResult()
        first_run = self.source.last_success_at is None and not self.source.checkpoint
        fetched = await self.fetch(dict(self.source.checkpoint or {}))
        result.checkpoint = fetched.checkpoint
        if fetched.not_modified:
            return result
        records: list[SkillRecord] = [r for r in fetched.records if isinstance(r, SkillRecord)]
        result.fetched = len(records)
        stats = await upsert(
            session, self.source.id, records, now, initial=first_run and self.initial_is_baseline
        )
        await self.reconcile_listing(session, records)
        result.created, result.updated, result.skipped = stats.created, stats.updated, stats.unchanged
        result.errors = list(self.errors)
        self.log_errors()
        return result

    # A marketplace's first collection lists what already existed (not "new"); the registry is read by date.
    initial_is_baseline = True


# ------------------------------------------------------------------------------------------- MCP Registry
class McpRegistryConfig(ConnectorConfig):
    initial_days: int = Field(
        7, ge=1, le=90, description="First run: servers published/updated this many days back"
    )
    page_size: int = Field(100, ge=1, le=100)
    max_pages: int = Field(
        30, ge=1, le=200, description="Pages per run; the next run resumes from the cursor"
    )


class McpRegistryConnector(_SkillConnector):
    key = "mcp_registry"
    description = "Official MCP Registry: new and updated MCP servers (latest versions)"
    Config = McpRegistryConfig
    config: McpRegistryConfig
    initial_is_baseline = False  # every server it returns was published or updated within the window

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        base = self.source.url.rstrip("/")
        since = checkpoint.get("updated_since") or (
            (self.now - timedelta(days=self.config.initial_days)).isoformat().replace("+00:00", "Z")
        )
        cursor: str | None = checkpoint.get("cursor")
        started = checkpoint.get("run_started") or (self.now - timedelta(minutes=5)).isoformat()  # overlap
        records: list[SkillRecord] = []
        for _ in range(self.config.max_pages):
            params: dict[str, Any] = {
                "limit": self.config.page_size,
                "version": "latest",
                "updated_since": since,
            }
            if cursor:
                params["cursor"] = cursor
            resp = await self.http.get(f"{base}/v0/servers", params=params, rate_limit=self.rate_limit)
            page = resp.json()
            for entry in page.get("servers") or []:
                try:
                    records.append(self._record(base, entry))
                except Exception as exc:  # noqa: BLE001 - one malformed entry must not abort the run
                    name = (entry.get("server") or {}).get("name")
                    self.record_error("normalize", f"{type(exc).__name__}: {exc}", ref=name)
            cursor = (page.get("metadata") or {}).get("nextCursor")
            if not cursor:
                # Complete: next run asks for what changed since this run started.
                return FetchResult(records, checkpoint={"updated_since": started.replace("+00:00", "Z")})
        # Page budget spent: resume from the cursor, same window, on the next run.
        return FetchResult(
            records, checkpoint={"updated_since": since, "cursor": cursor, "run_started": started}
        )

    def _record(self, base: str, entry: dict[str, Any]) -> SkillRecord:
        server = entry["server"]
        name = server["name"]
        meta = (entry.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
        repo = (server.get("repository") or {}).get("url")
        packages = [
            {k: p.get(k) for k in ("registryType", "identifier", "version", "runtimeHint") if p.get(k)}
            | {"transport": (p.get("transport") or {}).get("type")}
            for p in server.get("packages") or []
        ]
        remotes = [{"type": r.get("type"), "url": r.get("url")} for r in server.get("remotes") or []]
        return SkillRecord(
            kind=SkillKind.MCP_SERVER,
            name=name,
            title=server.get("title") or name,
            description=server.get("description"),
            version=server.get("version"),
            publisher=name.split("/", 1)[0],  # the namespace the registry verified (reverse DNS / GitHub)
            status=meta.get("status") or "active",
            listing_url=f"{base}/v0/servers/{quote(name, safe='')}/versions/latest",
            homepage_url=server.get("websiteUrl"),
            repository_url=repo,
            install=install.mcp_server(name, server),
            facts={"packages": packages, "remotes": remotes},
            published_at=parse_dt(meta.get("publishedAt")),
            source_updated_at=parse_dt(meta.get("updatedAt")),
        )


# --------------------------------------------------------------------------------- plugin marketplaces
def _repo_path(path: str) -> str | None:
    """A path relative to the repository root ("" for the root), or None when it leaves the repository."""
    norm = posixpath.normpath(path)
    if norm.startswith("/") or norm == ".." or norm.startswith("../"):
        return None
    return "" if norm == "." else norm


class MarketplaceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    ref: str = Field("main", pattern=r"^[A-Za-z0-9_./-]+$")
    path: str = Field(".claude-plugin/marketplace.json", pattern=r"^[A-Za-z0-9_./-]+$")


class ClaudeMarketplaceConfig(ConnectorConfig):
    marketplaces: list[MarketplaceRef] = Field(min_length=1, max_length=20)
    read_skills: bool = Field(True, description="Read the SKILL.md of every Agent Skill a plugin lists")


class ClaudeMarketplaceConnector(_SkillConnector):
    key = "claude_marketplace"
    description = "Claude Code plugin marketplaces: plugins and the Agent Skills they bundle"
    Config = ClaudeMarketplaceConfig
    config: ClaudeMarketplaceConfig

    def raw(self, repo: str, ref: str, path: str) -> str:
        return f"{self.source.url.rstrip('/')}/{repo}/{ref}/{path.lstrip('/')}"

    async def fetch(self, checkpoint: dict[str, Any]) -> FetchResult:
        listings: list[tuple[MarketplaceRef, dict[str, Any]]] = []
        hashes: dict[str, str] = {}
        for m in self.config.marketplaces:
            try:
                resp = await self.http.get(self.raw(m.repo, m.ref, m.path), rate_limit=self.rate_limit)
            except FetchError as exc:
                self.record_error("fetch", str(exc), ref=m.repo)
                continue
            hashes[m.repo] = hashlib.sha256(resp.content).hexdigest()
            listings.append((m, resp.json()))
        if not listings:
            raise FetchError(f"every marketplace failed: {self.errors[0]['error']}")
        self._complete = len(listings) == len(self.config.marketplaces)
        # Unchanged marketplace files: their skills are not read again either.
        if self._complete and hashes == checkpoint.get("sha256") and checkpoint.get("records"):
            return FetchResult([], checkpoint=checkpoint, not_modified=True)
        records: list[SkillRecord] = []
        for m, data in listings:
            records += await self._marketplace(m, data)
        return FetchResult(records, checkpoint={"sha256": hashes, "records": len(records)})

    async def _marketplace(self, m: MarketplaceRef, data: dict[str, Any]) -> list[SkillRecord]:
        market = data.get("name") or m.repo.split("/")[1]
        blob = f"https://github.com/{m.repo}/blob/{m.ref}/"
        out: list[SkillRecord] = []
        for p in data.get("plugins") or []:
            name = p.get("name")
            if not name:
                continue
            src = p.get("source")
            repo_url = src.get("url") if isinstance(src, dict) else None
            homepage = p.get("homepage")
            if not homepage and isinstance(src, str) and (folder := _repo_path(src)) is not None:
                homepage = f"https://github.com/{m.repo}/tree/{m.ref}/{folder}".rstrip("/")
            author = p.get("author") or {}
            out.append(SkillRecord(
                kind=SkillKind.PLUGIN, name=name, title=name, description=p.get("description"),
                version=p.get("version"), publisher=author.get("name") if isinstance(author, dict) else None,
                category=p.get("category"), listing_url=blob + m.path, homepage_url=homepage,
                repository_url=repo_url.removesuffix(".git") if repo_url else None,
                install=install.plugin(name, market, m.repo),
                facts={"marketplace": market, "marketplace_repo": m.repo,
                       "source": src if isinstance(src, (str, dict)) else None},
            ))  # fmt: skip
            if self.config.read_skills and isinstance(src, str):
                for skill_path in p.get("skills") or []:
                    rec = await self._skill(m, market, name, src, skill_path, blob)
                    if rec:
                        out.append(rec)
        return out

    async def _skill(
        self, m: MarketplaceRef, market: str, plugin: str, src: str, skill_path: str, blob: str
    ) -> SkillRecord | None:
        folder = _repo_path(posixpath.join(src, skill_path))
        if folder is None:
            self.record_error("normalize", f"skill path outside the repository: {skill_path}", ref=plugin)
            return None
        path = f"{folder}/SKILL.md" if folder else "SKILL.md"
        try:
            text = (await self.http.get(self.raw(m.repo, m.ref, path), rate_limit=self.rate_limit)).text
        except FetchError as exc:
            self.record_error("fetch", str(exc), ref=path)
            return None
        meta = frontmatter.parse(text)
        name = meta.get("name") or folder.rsplit("/", 1)[-1] or plugin
        return SkillRecord(
            kind=SkillKind.SKILL, name=name, title=name, description=meta.get("description"),
            publisher=None, category=plugin, listing_url=blob + path,
            homepage_url=f"https://github.com/{m.repo}/tree/{m.ref}/{folder}",
            install=install.skill(plugin, market, m.repo),
            facts={"marketplace": market, "marketplace_repo": m.repo, "plugin": plugin,
                   "license": meta.get("license")},
        )  # fmt: skip

    async def reconcile_listing(self, session: AsyncSession, records: list[SkillRecord]) -> None:
        if getattr(self, "_complete", False):  # only when every marketplace was read
            keep = {
                kind: {r.name for r in records if r.kind == kind}
                for kind in (SkillKind.PLUGIN, SkillKind.SKILL)
            }
            await mark_removed(session, self.source.id, keep)
