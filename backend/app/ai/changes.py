"""Release change detection: what changed between a release and the previous release of the same model,
tool or repository, taken only from what the two sources say.

Nothing here is generated. Each field is extracted from the release notes or source metadata of each side
and compared:

* version   - from the release record (GitHub tag, model release version);
* license   - from source metadata (e.g. Hugging Face) or an explicit "license ..." statement in the text;
* benchmarks - scores quoted next to a known benchmark name ("MMLU 85.2", "90.1% on HumanEval");
* changelog - the new release's own notes, grouped by their headings (breaking, features, fixes, other).

Every value carries the source it came from ("current" or "previous", with its URL), and anything a source
does not state is reported as "not documented" - never inferred.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.text import clean_text
from app.models import AIModelRelease, Article

VERSION = "changes-v1"
NOT_DOCUMENTED = "not documented"

# Benchmark names as sources write them (longest first, so "MMLU-Pro" wins over "MMLU").
BENCHMARKS = sorted(
    [
        "MMLU-Pro", "MMLU", "HumanEval+", "HumanEval", "MBPP", "GSM8K", "MATH-500", "MATH", "GPQA Diamond",
        "GPQA", "SWE-bench Verified", "SWE-bench", "LiveCodeBench", "BigCodeBench", "HellaSwag",
        "ARC-Challenge", "WinoGrande", "TruthfulQA", "IFEval", "BBH", "DROP", "AIME", "MT-Bench",
        "Arena-Hard", "MMMU", "ChartQA", "DocVQA",
    ],
    key=len,
    reverse=True,
)  # fmt: skip
_NUM = r"(\d{1,3}(?:\.\d{1,2})?)"
# Bounded gaps only (no nested or unbounded quantifiers): linear on any input.
_BENCH_AFTER = {
    b: re.compile(rf"(?<![\w-]){re.escape(b)}(?![\w-])[^\d\n]{{0,24}}?{_NUM}\s?%?", re.I) for b in BENCHMARKS
}
_BENCH_BEFORE = {b: re.compile(rf"{_NUM}\s?%?\s(?:on|in)\s{re.escape(b)}(?![\w-])", re.I) for b in BENCHMARKS}

_SPDX = (
    r"Apache[- ]2\.0|MIT|BSD-3-Clause|BSD-2-Clause|AGPL-3\.0|LGPL-3\.0|LGPL-2\.1|GPL-3\.0|GPL-2\.0|MPL-2\.0|"
    r"CC-BY-NC-SA-4\.0|CC-BY-NC-4\.0|CC-BY-SA-4\.0|CC-BY-4\.0|Unlicense|ISC"
)
_LICENSE = re.compile(rf"\blicen[cs](?:e|ed|ing)\b[^.\n]{{0,40}}?\b({_SPDX})\b", re.I)
_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s+|\*\*)(.{1,80}?)(?:\*\*)?\s*:?\s*$")
_BULLET = re.compile(r"^\s{0,6}(?:[-*•]|\d{1,3}[.)])\s+(.{3,})$")
_MD_LINK = re.compile(r"\[([^\]]{1,200})\]\([^)]{1,500}\)")
SECTION_KINDS = [
    ("breaking", re.compile(r"breaking|incompatib|removed|deprecat|migration", re.I)),
    ("security", re.compile(r"security|cve|vulnerab", re.I)),
    ("features", re.compile(r"feature|new|added|enhancement|highlight|what'?s changed|improve", re.I)),
    ("fixes", re.compile(r"fix|bug|patch", re.I)),
]
MAX_ITEMS_PER_SECTION = 12


@dataclass
class Snapshot:
    """One side of the comparison, with everything it says about itself."""

    article_id: uuid.UUID | None
    title: str
    url: str
    version: str | None
    published_at: datetime | None
    text: str
    license: str | None = None
    license_basis: str | None = None
    benchmarks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ref(self) -> dict[str, Any]:
        return {
            "article_id": str(self.article_id) if self.article_id else None,
            "title": self.title,
            "url": self.url,
            "version": self.version,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


# ----------------------------------------------------------------------------------- extraction
def _plain(text: str) -> str:
    return _MD_LINK.sub(r"\1", text)


def extract_benchmarks(text: str) -> dict[str, dict[str, Any]]:
    """{benchmark: {"value": float, "quote": line}} for scores the text states next to a benchmark name."""
    found: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        if not any(c.isdigit() for c in line):
            continue
        work = line
        for name in BENCHMARKS:
            if name in found:
                continue
            m = _BENCH_AFTER[name].search(work) or _BENCH_BEFORE[name].search(work)
            if m:
                value = float(m.group(1))
                if 0 <= value <= 100 or name == "MT-Bench":
                    found[name] = {"value": value, "quote": _plain(line.strip())[:200]}
                # Hide the match so "MMLU" does not re-read the number of "MMLU-Pro" on the same line.
                work = work[: m.start()] + " " * (m.end() - m.start()) + work[m.end() :]
    return found


def extract_license(text: str, metadata: str | None) -> tuple[str | None, str | None]:
    """(license, basis). Source metadata wins; otherwise an explicit 'license ... <SPDX id>' statement."""
    if metadata and metadata.strip().lower() not in ("", "other", "unknown"):
        return metadata.strip(), "source metadata"
    m = _LICENSE.search(text)
    if m:
        return m.group(1).replace(" ", "-"), _plain(text[max(0, m.start() - 20) : m.end() + 20].strip())[:160]
    return None, None


def changelog_sections(text: str) -> list[dict[str, Any]]:
    """The release's own bullet points, grouped under their headings."""
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        b = _BULLET.match(line)
        if b:
            if current is None:
                current = {"heading": "Changes", "kind": "other", "items": []}
                sections.append(current)
            if len(current["items"]) < MAX_ITEMS_PER_SECTION:
                current["items"].append(_plain(b.group(1)).strip()[:240])
            continue
        h = _HEADING.match(line)
        if h:
            heading = _plain(h.group(1)).strip(" *#:")
            kind = next((k for k, rx in SECTION_KINDS if rx.search(heading)), "other")
            current = {"heading": heading[:80], "kind": kind, "items": []}
            sections.append(current)
    return [s for s in sections if s["items"]]


def version_bump(previous: str | None, current: str | None) -> str | None:
    def parts(v: str | None) -> list[int] | None:
        m = re.match(r"^\D{0,10}?(\d{1,6})(?:\.(\d{1,6}))?(?:\.(\d{1,6}))?", v or "")
        return [int(x or 0) for x in m.groups()] if m else None

    p, c = parts(previous), parts(current)
    if not p or not c:
        return None
    if c[0] != p[0]:
        return "major"
    if c[1] != p[1]:
        return "minor"
    return "patch" if c[2] != p[2] else "none"


# ----------------------------------------------------------------------------------- comparison
def compare(current: Snapshot, previous: Snapshot) -> dict[str, Any]:
    cites = {"current": current.url, "previous": previous.url}

    if current.license and previous.license:
        same = current.license.lower() == previous.license.lower()
        lic_status = "unchanged" if same else "changed"
    elif current.license or previous.license:
        lic_status = "documented in one source only"
    else:
        lic_status = NOT_DOCUMENTED
    license_out = {
        "status": lic_status,
        "current": {"value": current.license or NOT_DOCUMENTED, "basis": current.license_basis},
        "previous": {"value": previous.license or NOT_DOCUMENTED, "basis": previous.license_basis},
    }

    benchmarks = []
    for name in sorted(set(current.benchmarks) | set(previous.benchmarks)):
        cur, prev = current.benchmarks.get(name), previous.benchmarks.get(name)
        if cur and prev:
            delta = round(cur["value"] - prev["value"], 2)
            status = "unchanged" if delta == 0 else "changed"
        else:
            delta, status = None, "only in current" if cur else "only in previous"
        benchmarks.append(
            {
                "name": name,
                "current": cur["value"] if cur else NOT_DOCUMENTED,
                "previous": prev["value"] if prev else NOT_DOCUMENTED,
                "delta": delta,
                "status": status,
                "quotes": {
                    "current": cur["quote"] if cur else None,
                    "previous": prev["quote"] if prev else None,
                },
            }
        )

    sections = changelog_sections(current.text)
    return {
        "version": VERSION,
        "current": current.ref(),
        "previous": previous.ref(),
        "version_change": {
            "from": previous.version or NOT_DOCUMENTED,
            "to": current.version or NOT_DOCUMENTED,
            "bump": version_bump(previous.version, current.version),
        },
        "license": license_out,
        "benchmarks": benchmarks,
        "benchmarks_status": "documented" if benchmarks else NOT_DOCUMENTED,
        "changelog": {
            "status": "documented" if sections else NOT_DOCUMENTED,
            "source": "current",
            "sections": sections,
        },
        "citations": cites,
        "method": "Rule-based comparison of the two source texts. Nothing is generated or inferred.",
    }


# ----------------------------------------------------------------------------------- lookup
def _article_snapshot(a: Article, version: str | None, license_meta: str | None = None) -> Snapshot:
    text = clean_text("\n".join(filter(None, [a.title, a.content or a.description])))
    lic, basis = extract_license(text, license_meta)
    return Snapshot(
        article_id=a.id,
        title=a.title,
        url=a.url,
        version=version,
        published_at=a.published_at,
        text=a.content or a.description or "",
        license=lic,
        license_basis=basis,
        benchmarks=extract_benchmarks(text),
    )


def _gh_release(a: Article) -> tuple[str, str] | None:
    """(repo, tag) of a GitHub release item (canonical key gh-release:<owner/name>:<tag>)."""
    key = a.canonical_key or ""
    if not key.startswith("gh-release:"):
        return None
    _, repo, tag = key.split(":", 2)
    return repo, tag


def _license_meta(a: Article) -> str | None:
    lic = (a.raw or {}).get("license") if isinstance(a.raw, dict) else None
    return lic if isinstance(lic, str) else None


async def detect(session: AsyncSession, a: Article) -> dict[str, Any] | None:
    """The comparison for a release item, or None when it is not a release or has no previous release."""
    gh = _gh_release(a)
    if gh is not None:
        repo, tag = gh
        when = a.published_at or a.collected_at
        prev = await session.scalar(
            select(Article)
            .where(
                Article.canonical_key.like(f"gh-release:{repo}:%"),
                Article.id != a.id,
                Article.duplicate_of_id.is_(None),
                Article.published_at < when,
            )
            .order_by(Article.published_at.desc())
            .limit(1)
        )
        if prev is None:
            return None
        prev_tag = _gh_release(prev)
        return compare(
            _article_snapshot(a, tag, _license_meta(a)),
            _article_snapshot(prev, prev_tag[1] if prev_tag else None, _license_meta(prev)),
        )

    rel = await session.scalar(select(AIModelRelease).where(AIModelRelease.article_id == a.id))
    if rel is None or rel.released_at is None:
        return None
    prev_rel = await session.scalar(
        select(AIModelRelease)
        .where(
            AIModelRelease.model_id == rel.model_id,
            AIModelRelease.id != rel.id,
            AIModelRelease.released_at < rel.released_at,
        )
        .order_by(AIModelRelease.released_at.desc())
        .limit(1)
    )
    if prev_rel is None:
        return None
    current = _article_snapshot(a, rel.version, _license_meta(a))
    prev_article = await session.get(Article, prev_rel.article_id) if prev_rel.article_id else None
    if prev_article is not None:
        previous = _article_snapshot(prev_article, prev_rel.version, _license_meta(prev_article))
    else:  # the earlier release is known only as a record: compare what that record states
        notes = prev_rel.notes or ""
        lic, basis = extract_license(notes, None)
        previous = Snapshot(
            article_id=None,
            title=f"{prev_rel.version or 'previous release'}",
            url=prev_rel.source_url,
            version=prev_rel.version,
            published_at=prev_rel.released_at,
            text=notes,
            license=lic,
            license_basis=basis,
            benchmarks=extract_benchmarks(notes),
        )
    return compare(current, previous)
