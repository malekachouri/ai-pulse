"""Bug Intelligence: why a bug or vulnerability occurs, its impact, the affected versions and the available
fixes, taken only from the official sources AI Pulse collected about it.

Sources, numbered [1], [2], ... and returned with their links:
* the item itself (GitHub issue, security advisory, CVE record as collected);
* the structured record (CVE: NVD/advisory fields; bug: the tracked issue and its linked fix);
* the same CVE as collected from other official sources (vendor advisory, GitHub advisory);
* release notes that mention the CVE id or the issue (fix evidence).

Each section has two layers:
* facts  - copied from structured fields (CWE, CVSS, KEV, affected ranges, remediation, fixed-in version),
           each with the number of the source it came from;
* text   - an optional LLM explanation written from the numbered sources only. It must cite them; it is then
           grounded (sentences with numbers, versions or ids that the cited sources do not contain are
           removed) and, for fixes, kept only when a cited source documents a fix.
A section with neither facts nor grounded text says "insufficient information". Without an LLM the
facts are still served (status "facts_only").
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import claims
from app.ai.pipeline import _article_text, record_usage, upsert_analysis
from app.ai.providers import AIProviders, ProviderError
from app.models import AIAnalysis, Article, SecurityVulnerability, SoftwareBug
from app.models.enums import AnalysisKind, ItemType

VERSION = "bugintel-v1"
INSUFFICIENT = "insufficient information"
SECTIONS = ("cause", "impact", "affected_versions", "fixes")
BUG_TYPES = (ItemType.BUG, ItemType.VULNERABILITY, ItemType.GITHUB_ISSUE)
RELEASE_TYPES = (ItemType.MODEL_RELEASE, ItemType.TOOL, ItemType.GITHUB_REPO, ItemType.NEWS)
MAX_RELATED = 4
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}")

SYSTEM_BUG_INTEL = """You explain ONE software bug or vulnerability to an engineer.
Use ONLY the numbered sources.
For each section write 1-3 plain sentences and cite the sources you used by number.
- cause: why the problem occurs (the defect or weakness)
- impact: what an attacker or user can trigger and what breaks
- affected_versions: which versions or products are affected
- fixes: the fix, patched versions or workaround the sources document
If the sources do not say, set text to null and citations to []. Never add versions, numbers or fixes that
the sources do not contain. JSON only."""


class Part(BaseModel):
    text: str | None = Field(None, max_length=900)
    citations: list[int] = Field(default_factory=list, max_length=6)


class BugExplanation(BaseModel):
    cause: Part = Field(default_factory=Part)
    impact: Part = Field(default_factory=Part)
    affected_versions: Part = Field(default_factory=Part)
    fixes: Part = Field(default_factory=Part)


@dataclass
class Src:
    n: int
    kind: str  # issue | advisory | cve_record | bug_record | release_notes | fix
    title: str
    url: str
    text: str
    published_at: datetime | None = None
    documents_fix: bool = False

    def ref(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "kind": self.kind,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


def product_line(p: dict[str, Any]) -> str:
    """One affected product as the source states it (NVD CPE ranges or a GitHub advisory range)."""
    name = " ".join(x for x in (p.get("vendor"), p.get("ecosystem"), p.get("product")) if x)
    parts = [name or "product"]
    if p.get("version"):
        parts.append(str(p["version"]))
    if p.get("vulnerable_range"):
        parts.append(str(p["vulnerable_range"]))
    for key, op in (
        ("versionStartIncluding", ">="),
        ("versionStartExcluding", ">"),
        ("versionEndIncluding", "<="),
        ("versionEndExcluding", "<"),
    ):
        if p.get(key):
            parts.append(f"{op} {p[key]}")
    return " ".join(parts)


def _fact(text: str, n: int) -> dict[str, Any]:
    return {"text": text, "citation": n}


class BugIntelligence:
    def __init__(self, session: AsyncSession, providers: AIProviders, now: datetime | None = None) -> None:
        self.s = session
        self.p = providers
        self.now = now or datetime.now(UTC)

    # ------------------------------------------------------------------------------ sources
    async def gather(self, a: Article) -> tuple[dict[str, Any], list[Src], dict[str, list[dict[str, Any]]]]:
        sources: list[Src] = []
        facts: dict[str, list[dict[str, Any]]] = {k: [] for k in SECTIONS}

        def add(**kw: Any) -> Src:
            src = Src(n=len(sources) + 1, **kw)
            sources.append(src)
            return src

        vuln = await self.s.scalar(
            select(SecurityVulnerability).where(SecurityVulnerability.article_id == a.id)
        )
        cve = vuln.cve_id if vuln else (CVE_RE.search(a.canonical_key or a.title or "") or [None])[0]
        if vuln is None and cve:
            vuln = await self.s.scalar(
                select(SecurityVulnerability).where(SecurityVulnerability.cve_id == cve)
            )
        bug = await self.s.scalar(select(SoftwareBug).where(SoftwareBug.article_id == a.id))

        own_kind = "issue" if a.item_type != ItemType.VULNERABILITY else (
            "cve_record" if a.source.connector == "nvd" else "advisory"
        )  # fmt: skip
        item = add(
            kind=own_kind,
            title=a.title,
            url=a.url,
            text=_article_text(a)[:8000],
            published_at=a.published_at,
            documents_fix=bool(vuln and vuln.remediation and a.source.connector != "nvd"),
        )

        if vuln is not None:
            lines = [f"{vuln.cve_id}: {vuln.description or ''}"]
            products = [product_line(p) for p in (vuln.affected_products or [])[:20]]
            if products:
                lines.append("Affected: " + "; ".join(products))
            if vuln.cvss_score is not None:
                lines.append(
                    f"CVSS {vuln.cvss_version or ''} base score {vuln.cvss_score} {vuln.cvss_vector or ''}"
                )
            if vuln.cwe_ids:
                lines.append("Weakness: " + ", ".join(vuln.cwe_ids))
            if vuln.known_exploited:
                lines.append(f"Known exploited (CISA KEV), added {vuln.kev_date_added}")
            if vuln.remediation:
                lines.append(f"Remediation: {vuln.remediation}")
            rec = add(
                kind="cve_record",
                title=f"{vuln.cve_id} record",
                url=f"https://nvd.nist.gov/vuln/detail/{vuln.cve_id}",
                text="\n".join(lines),
                published_at=vuln.published_at,
                documents_fix=bool(vuln.remediation),
            )
            if vuln.cwe_ids:
                facts["cause"].append(_fact("Weakness: " + ", ".join(vuln.cwe_ids), rec.n))
            if vuln.cvss_score is not None:
                facts["impact"].append(
                    _fact(
                        f"CVSS {vuln.cvss_score} ({vuln.severity.value})"
                        + (f", vector {vuln.cvss_vector}" if vuln.cvss_vector else ""),
                        rec.n,
                    )
                )
            if vuln.known_exploited:
                facts["impact"].append(
                    _fact(f"Actively exploited: listed in CISA KEV since {vuln.kev_date_added}", rec.n)
                )
            facts["affected_versions"] += [_fact(p, rec.n) for p in products]
            if vuln.remediation:
                facts["fixes"].append(_fact(vuln.remediation, rec.n))
            elif vuln.patch_available is False:
                facts["fixes"].append(_fact("The record states that no patch is available", rec.n))
            # The same CVE collected from other official channels (vendor or GitHub advisories).
            others = (
                await self.s.scalars(
                    select(Article)
                    .where(Article.canonical_key == f"cve:{vuln.cve_id}", Article.id != a.id)
                    .order_by(Article.published_at.desc().nulls_last())
                    .limit(MAX_RELATED)
                )
            ).unique()
            for o in others:
                add(kind="advisory", title=o.title, url=o.url, text=_article_text(o)[:4000],
                    published_at=o.published_at)  # fmt: skip

        if bug is not None:
            lines = [f"Project: {bug.project}", f"Status: {bug.status.value}"]
            if bug.severity_basis:
                lines.append(f"Severity {bug.severity.value} (basis: {bug.severity_basis})")
            if bug.affected_versions:
                lines.append("Affected versions: " + ", ".join(bug.affected_versions))
            if bug.fixed_in_version:
                lines.append(f"Fixed in {bug.fixed_in_version}")
            if bug.resolution:
                lines.append(f"Resolution: {bug.resolution.value}")
            has_fix = bool(bug.fixed_in_version or bug.fix_url)
            rec = add(kind="bug_record", title=f"{bug.project} issue record", url=bug.source_url,
                      text="\n".join(lines), published_at=a.published_at, documents_fix=has_fix)  # fmt: skip
            if bug.severity_basis:
                facts["impact"].append(
                    _fact(f"Severity {bug.severity.value} (basis: {bug.severity_basis})", rec.n)
                )
            facts["affected_versions"] += [_fact(v, rec.n) for v in bug.affected_versions]
            if bug.fix_url:
                fix = add(kind="fix", title="Linked fix", url=bug.fix_url,
                          text=f"Fix for {bug.project}" + (f", released in {bug.fixed_in_version}"
                                                            if bug.fixed_in_version else ""),
                          published_at=bug.fix_merged_at, documents_fix=True)  # fmt: skip
                facts["fixes"].append(
                    _fact(
                        "Fixed by the linked change"
                        + (f" (merged {bug.fix_merged_at:%Y-%m-%d})" if bug.fix_merged_at else ""),
                        fix.n,
                    )
                )
            if bug.fixed_in_version:
                facts["fixes"].append(_fact(f"Fixed in {bug.fixed_in_version}", rec.n))

        # Release notes that mention the CVE id or this issue: evidence of a fix.
        needle = cve or None
        repo_key = None
        if bug is not None and bug.github_issue is not None:
            needle = f"#{bug.github_issue.number}"
            repo_key = f"gh-release:{bug.project.lower()}:%"
        if needle:
            stmt = select(Article).where(
                Article.item_type.in_(RELEASE_TYPES),
                Article.id != a.id,
                Article.content.ilike(f"%{needle}%"),
            )
            if repo_key:
                stmt = stmt.where(Article.canonical_key.like(repo_key))
            notes = (
                await self.s.scalars(
                    stmt.order_by(Article.published_at.desc().nulls_last()).limit(MAX_RELATED)
                )
            ).unique()
            for o in notes:
                if needle.startswith("#") and not re.search(rf"{re.escape(needle)}(?!\d)", o.content or ""):
                    continue  # "#12" must not match "#123"
                src = add(kind="release_notes", title=o.title, url=o.url, text=_article_text(o)[:4000],
                          published_at=o.published_at, documents_fix=True)  # fmt: skip
                facts["fixes"].append(_fact(f"Mentioned in the release notes of {o.title}", src.n))

        subject = {
            "kind": "vulnerability" if vuln is not None or a.item_type == ItemType.VULNERABILITY else "bug",
            "id": cve
            or (f"{bug.project}#{bug.github_issue.number}" if bug and bug.github_issue else a.title[:80]),
            "title": a.title,
            "article_id": str(a.id),
            "url": item.url,
        }
        return subject, sources, facts

    # ------------------------------------------------------------------------------ explanation
    def ground(
        self, data: BugExplanation, sources: list[Src], facts: dict[str, list[dict[str, Any]]]
    ) -> tuple[dict[str, Any], list[str]]:
        by_n = {s.n: s for s in sources}
        removed: set[str] = set()
        out: dict[str, Any] = {}
        for key in SECTIONS:
            part: Part = getattr(data, key)
            cites = [n for n in dict.fromkeys(part.citations) if n in by_n]
            text = None
            if part.text and cites:
                cited_text = "\n".join(by_n[n].text for n in cites)
                kept, bad = claims.strip_unsupported(part.text, cited_text)
                removed.update(bad)
                if key == "fixes" and not any(by_n[n].documents_fix for n in cites):
                    kept = ""  # never present a fix that no cited source documents
                text = kept or None
            out[key] = self._section(key, facts[key], text, cites if text else [])
        return out, sorted(removed)

    @staticmethod
    def _section(key: str, facts: list[dict[str, Any]], text: str | None, cites: list[int]) -> dict[str, Any]:
        documented = bool(facts or text)
        return {
            "status": "documented" if documented else "insufficient",
            "text": text if text else (None if facts else INSUFFICIENT),
            "text_is_ai": bool(text),
            "citations": cites,
            "facts": facts,
        }

    async def build(self, a: Article, *, use_llm: bool) -> dict[str, Any]:
        if a.item_type not in BUG_TYPES:
            raise ValueError("Bug intelligence is only available for bugs, issues and vulnerabilities")
        subject, sources, facts = await self.gather(a)
        llm = self.p.llm if use_llm else None
        provider = model = None
        removed: list[str] = []
        sections = {k: self._section(k, facts[k], None, []) for k in SECTIONS}
        if llm is not None:
            prompt = "\n\n".join(
                [f"Subject: {subject['id']} - {subject['title']}"]
                + [f"[{s.n}] {s.kind}: {s.title} ({s.url})\n{s.text}" for s in sources]
            )
            try:
                result = await llm.complete_json(SYSTEM_BUG_INTEL, prompt[:24000], BugExplanation)
            except ProviderError as exc:
                await record_usage(self.s, "bug_intel", llm.provider, llm.model, ok=False, error=str(exc),
                                   article_id=a.id)  # fmt: skip
            else:
                await record_usage(self.s, "bug_intel", llm.provider, llm.model,
                                   input_tokens=result.usage.input_tokens,
                                   output_tokens=result.usage.output_tokens, cost=result.cost_usd,
                                   article_id=a.id)  # fmt: skip
                sections, removed = self.ground(result.data, sources, facts)
                provider, model = llm.provider, llm.model
        return {
            "subject": subject,
            "status": "ready" if provider else "facts_only",
            "sections": sections,
            "sources": [s.ref() for s in sources],
            "unsupported_claims_removed": removed,
            "ai_generated": bool(provider) and any(v["text_is_ai"] for v in sections.values()),
            "provider": provider,
            "model": model,
            "generated_at": self.now.isoformat(),
        }

    async def cached(self, a: Article) -> dict[str, Any] | None:
        row = await self.s.scalar(
            select(AIAnalysis).where(
                AIAnalysis.article_id == a.id,
                AIAnalysis.kind == AnalysisKind.BUG_INTEL,
                AIAnalysis.prompt_version == VERSION,
            )
        )
        return row.output if row else None

    async def generate(self, a: Article) -> dict[str, Any]:
        out = await self.build(a, use_llm=True)
        if out["status"] == "ready":
            await upsert_analysis(self.s, a.id, AnalysisKind.BUG_INTEL, VERSION, output=out,
                                  provider=out["provider"], model=out["model"])  # fmt: skip
        return out
