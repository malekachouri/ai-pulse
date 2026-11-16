""" "What is it good for?": an on-demand AI explanation of one Skills Radar entry, for any project.

Sources, numbered and returned with their links (only the tool's own material: the explanation is general,
not tied to one project):
  [1] the official listing as collected (description, version, publisher, install instructions, packages);
  [2] the project's README, when the listing links a GitHub repository (read on demand, trimmed).
The model writes four short sections from those sources only and cites them. Then:
  * uncited text and citations to unknown sources are dropped;
  * sentences with numbers, versions or ids that the cited sources do not contain are removed (claims.py).
A section left empty says "insufficient information". The result is stored on the entry, labelled
AI-generated, with the provider, model and listing version it was written for.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import claims
from app.ai.pipeline import record_usage
from app.ai.providers import AIProviders, ProviderError
from app.db.session import allow_slow_external_calls
from app.ingestion.http import FetchError, HttpClient
from app.models import AISkill

VERSION = "skill-explain-v2"  # v2: general use cases, no project-specific source
INSUFFICIENT = "insufficient information"
SECTIONS = ("what_it_does", "use_cases", "how_to_try", "cautions")
README_CHARS = 6000  # small local models: keep the prompt short
GITHUB_REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")

SYSTEM_SKILL_EXPLAIN = """You explain ONE tool for AI assistants (an MCP server, a Claude Code plugin or an
Agent Skill) to a developer who may use it in any kind of project. Use ONLY the numbered sources.
Write 1-3 plain sentences per section and cite the sources you used by number.
- what_it_does: what the tool does
- use_cases: the kinds of projects and tasks it is useful for, as the sources describe them
- how_to_try: how to install or try it, from the sources
- cautions: what to check before using it (secrets it needs, access it gets, maintenance, status)
If the sources do not support a section, set text to null and citations to []. Never invent features,
commands, versions or numbers. JSON only."""


class Part(BaseModel):
    text: str | None = Field(None, max_length=900)
    citations: list[int] = Field(default_factory=list, max_length=4)


class SkillExplanation(BaseModel):
    what_it_does: Part = Field(default_factory=Part)
    use_cases: Part = Field(default_factory=Part)
    how_to_try: Part = Field(default_factory=Part)
    cautions: Part = Field(default_factory=Part)


@dataclass
class Src:
    n: int
    kind: str  # listing | readme
    title: str
    url: str | None
    text: str

    def ref(self) -> dict[str, Any]:
        return {"n": self.n, "kind": self.kind, "title": self.title, "url": self.url}


def listing_text(s: AISkill) -> str:
    lines = [f"Name: {s.name}", f"Kind: {s.kind.value}"]
    fields = (("Title", s.title), ("Version", s.version), ("Publisher", s.publisher),
              ("Category", s.category), ("Status", s.status), ("Description", s.description))  # fmt: skip
    for label, value in fields:
        if value:
            lines.append(f"{label}: {value}")
    for step in s.install or []:
        lines.append(f"Install - {step.get('label')}: {step.get('command') or 'no command'}")
        lines += [f"  Note: {n}" for n in step.get("notes") or []]
    for p in (s.facts or {}).get("packages") or []:
        lines.append("Package: " + ", ".join(f"{k}={v}" for k, v in p.items() if v))
    for r in (s.facts or {}).get("remotes") or []:
        lines.append(f"Remote: {r.get('type')} {r.get('url')}")
    return "\n".join(lines)


def readme_url(repository_url: str | None) -> str | None:
    m = GITHUB_REPO_RE.match(repository_url or "")
    return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/HEAD/README.md" if m else None


def clean_readme(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images and badges
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:README_CHARS]


class SkillExplainer:
    def __init__(
        self, session: AsyncSession, providers: AIProviders, http: HttpClient | None = None,
        now: datetime | None = None,
    ) -> None:  # fmt: skip
        self.s = session
        self.p = providers
        self.http = http
        self.now = now or datetime.now(UTC)

    async def sources(self, skill: AISkill) -> list[Src]:
        out = [Src(1, "listing", f"Official listing: {skill.title or skill.name}", skill.listing_url,
                   listing_text(skill))]  # fmt: skip
        url = readme_url(skill.repository_url)
        if url and self.http is not None:
            try:
                resp = await self.http.get(url)
            except FetchError:
                pass  # no README: the listing alone may still be enough
            else:
                text = clean_readme(resp.text)
                if text:
                    out.append(Src(2, "readme", "Project README", skill.repository_url, text))
        return out

    def ground(self, data: SkillExplanation, sources: list[Src]) -> tuple[dict[str, Any], list[str]]:
        by_n = {s.n: s for s in sources}
        removed: set[str] = set()
        out: dict[str, Any] = {}
        for key in SECTIONS:
            part: Part = getattr(data, key)
            cites = [n for n in dict.fromkeys(part.citations) if n in by_n]
            text = None
            if part.text and cites:
                kept, bad = claims.strip_unsupported(part.text, "\n".join(by_n[n].text for n in cites))
                removed.update(bad)
                text = kept or None
            out[key] = {
                "text": text or INSUFFICIENT,
                "insufficient": not text,
                "citations": cites if text else [],
            }
        return out, sorted(removed)

    async def generate(self, skill: AISkill) -> dict[str, Any]:
        llm = self.p.llm
        if llm is None:
            raise ValueError("Explanations need an LLM provider (LLM_PROVIDER / LLM_MODEL).")
        sources = await self.sources(skill)
        prompt = "\n\n".join(f"[{s.n}] {s.title}{f' ({s.url})' if s.url else ''}\n{s.text}" for s in sources)
        await allow_slow_external_calls(self.s)
        try:
            result = await llm.complete_json(SYSTEM_SKILL_EXPLAIN, prompt[:16000], SkillExplanation)
        except ProviderError as exc:
            await record_usage(self.s, "skill_explain", llm.provider, llm.model, ok=False, error=str(exc))
            # Not stored: a previous explanation, if any, stays. The usage row records the failure.
            return {"status": "failed", "error": str(exc)[:300], "provider": llm.provider, "model": llm.model}
        await record_usage(self.s, "skill_explain", llm.provider, llm.model,
                           input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens,
                           cost=result.cost_usd)  # fmt: skip
        sections, removed = self.ground(result.data, sources)
        out = {
            "status": "ready" if any(not v["insufficient"] for v in sections.values()) else "insufficient",
            "sections": sections,
            "sources": [s.ref() for s in sources],
            "unsupported_claims_removed": removed,
            "ai_generated": True,
            "provider": llm.provider,
            "model": llm.model,
            "generated_at": self.now.isoformat(),
            "listing_version": skill.version,
            "prompt_version": VERSION,
        }
        skill.explanation = out
        await self.s.flush()
        return out
