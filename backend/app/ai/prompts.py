"""Versioned prompts and output schemas. Bump PROMPT_VERSION when prompts change: analyses are keyed by it."""

from typing import Literal

from pydantic import BaseModel, Field

PROMPT_VERSION = "v1"

CATEGORY_SLUGS = [
    "ai-models",
    "ai-research",
    "ai-tools",
    "rag",
    "llmops",
    "mlops",
    "ai-agents",
    "software-engineering",
    "bugs",
    "infrastructure-failures",
    "cybersecurity",
    "devops",
    "cloud",
    "kubernetes",
    "docker",
]

SYSTEM_ANALYST = """You are AI Pulse's technical analyst. You analyse ONE item collected from an official source.
Rules:
- Use ONLY facts stated in the SOURCE section. Never add versions, dates, scores, CVE ids, numbers or names
  that are not in the source. If something is unknown, say "Not stated in the source."
- Recommended actions for vulnerabilities: only if TRUSTED REMEDIATION is provided; otherwise recommend
  checking the vendor advisory and say no official remediation was provided.
- Do not speculate about exploitation, impact scale or affected users beyond what the source says.
- Categories must be chosen from the provided list. Multiple categories are allowed.
- Be concise and technical. Output JSON only."""


class Entity(BaseModel):
    type: Literal["organization", "product", "technology", "model", "person", "cve", "other"]
    name: str = Field(max_length=120)


class TechnicalImpact(BaseModel):
    level: Literal["high", "medium", "low", "none", "unknown"]
    description: str = Field(max_length=800)


class ItemAnalysis(BaseModel):
    short_summary: str = Field(max_length=400, description="1-2 sentences")
    detailed_explanation: str = Field(max_length=2500)
    what_happened: str = Field(max_length=800)
    why_it_matters: str = Field(max_length=800)
    who_is_affected: str = Field(max_length=600)
    technical_impact: TechnicalImpact
    recommended_actions: list[str] = Field(default_factory=list, max_length=6)
    related_technologies: list[str] = Field(default_factory=list, max_length=10)
    categories: list[str] = Field(default_factory=list, max_length=6)
    entities: list[Entity] = Field(default_factory=list, max_length=15)
    learning_topics: list[str] = Field(default_factory=list, max_length=4, description="Topics, no URLs")


def analysis_prompt(
    *,
    item_type: str,
    title: str,
    source: str,
    published: str | None,
    url: str,
    body: str,
    structured: str,
    remediation: str | None,
) -> str:
    return f"""ITEM TYPE: {item_type}
ALLOWED CATEGORIES: {", ".join(CATEGORY_SLUGS)}

SOURCE ({source}, published {published or "date not stated"}, {url})
Title: {title}
{body}

STRUCTURED FACTS FROM THE SOURCE:
{structured or "none"}

TRUSTED REMEDIATION: {remediation or "none provided by an official source"}

Produce the analysis JSON."""


SYSTEM_RAG = """You answer questions using ONLY the numbered sources provided. Each source was collected from an
official channel. Rules:
- Every factual sentence must cite at least one source like [1] or [2][3].
- Do not use outside knowledge. Do not invent numbers, versions, dates or names.
- If the sources do not contain enough information to answer, set "insufficient" to true and explain briefly
  what is missing instead of guessing.
- Be concise (at most ~200 words). Output JSON only."""


class RagAnswer(BaseModel):
    answer: str = Field(max_length=3000)
    insufficient: bool = False
    confidence: Literal["low", "medium", "high"] = "low"


SYSTEM_BRIEFING = """You write the executive summary of a daily technology briefing using ONLY the listed items.
Mention the 3-5 most important points, cite items as [n]. No outside facts, no invented numbers. JSON only."""


class BriefingSummary(BaseModel):
    executive_summary: str = Field(max_length=1500)
