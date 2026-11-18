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

VERSION = "skill-explain-v3"  # v3: required fields, example reply, matched citations, reasons
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
Every section needs "text" and "citations" (the numbers of the sources it comes from, e.g. [1] or [1, 2]).
If the sources do not support a section, set text to null and citations to []. Never invent features,
commands, versions or numbers. Reply with JSON only, shaped like this example:
{"what_it_does": {"text": "It converts PDF files to text.", "citations": [1]},
 "use_cases": {"text": "Useful in projects that index documents.", "citations": [1, 2]},
 "how_to_try": {"text": "Install it with the command from the listing.", "citations": [1]},
 "cautions": {"text": null, "citations": []}}"""

# A sentence the model did not cite is matched to a source when most of its words come from that source.
MATCH_SHARE = 0.6
MATCH_MIN_WORDS = 3
_WORD_RE = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_STOP = frozenset(
    "the and for with that this from into your you are can its use used using will which when what how "
    "they them their has have not but all any also more most such other about than then there these those "
    "via per may must should could would been being was were does".split()
)


class Part(BaseModel):
    # Required (no defaults): with a JSON-schema constrained reply, optional fields let a small model
    # answer with empty sections.
    text: str | None = Field(max_length=900)
    citations: list[int] = Field(max_length=4)


class SkillExplanation(BaseModel):
    what_it_does: Part
    use_cases: Part
    how_to_try: Part
    cautions: Part


def _words(text: str) -> set[str]:
    return {w.strip(".-") for w in _WORD_RE.findall(text.lower())} - _STOP


def matching_sources(text: str, sources: list[Src]) -> list[int]:
    """Sources that contain most of the text's words: used when the model wrote a section without citing."""
    words = _words(text)
    if len(words) < MATCH_MIN_WORDS:
        return []
    out = []
    for s in sources:
        shared = words & _words(s.text)
        if len(shared) >= MATCH_MIN_WORDS and len(shared) / len(words) >= MATCH_SHARE:
            out.append(s.n)
    return out


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
            matched = False
            text = None
            reason = None
            if not (part.text or "").strip():
                reason = "the model wrote nothing for this section"
            else:
                if not cites:  # small models often leave citations empty: match the text to a source instead
                    cites = matching_sources(part.text or "", sources)
                    matched = bool(cites)
                if not cites:
                    reason = "the model's text matches no source"
                else:
                    kept, bad = claims.strip_unsupported(
                        part.text or "", "\n".join(by_n[n].text for n in cites)
                    )
                    removed.update(bad)
                    text = kept or None
                    if not text:
                        reason = "the model's text contained claims the sources do not support"
            out[key] = {
                "text": text or INSUFFICIENT,
                "insufficient": not text,
                "citations": cites if text else [],
                "citations_matched": bool(text) and matched,
                "reason": reason,
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
