"""Versions and fixes that an official text states, read without AI and quoted as written.

Used by Bug Intelligence (quoted facts) and by the analysis pipeline (a fix the CVE description states is an
official remediation). Bounded repetitions only, so the patterns stay linear on any input.
"""

import re

# Versions an official text states: "before 0.11.0", "prior to 0.31.8", "fixed in 2.4.1", "upgrade to 3.0".
# Bounded repetitions only (linear on any input).
_VER = r"v?\d{1,4}(?:\.\d{1,6}){1,3}(?:[-+][0-9A-Za-z.]{1,20})?"
_AFFECTED_RE = re.compile(
    rf"\b(?:before|prior to|earlier than|older than|up to and including|through)\s{{1,3}}"
    rf"(?:version\s{{1,3}}|v\s{{0,1}})?{_VER}",
    re.I,
)
_FIX_RE = re.compile(
    rf"\b(?:(?:fixed|patched|resolved|addressed|remediated)\s{{1,3}}in|(?:upgrade|update)\s{{1,3}}to)\s{{1,3}}"
    rf"(?:version\s{{1,3}})?{_VER}",
    re.I,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s{1,5}(?=[A-Z])")
MAX_STATED = 3


def stated(text: str, pattern: re.Pattern[str]) -> list[str]:
    """Sentences of an official text that state affected or fixed versions, quoted (shortened when long)."""
    out: list[str] = []
    for sentence in _SENTENCE_RE.split(text or ""):
        sentence = " ".join(sentence.split())
        if sentence.endswith(("…", "...")):
            continue  # a cut-off headline: the full sentence is in the description
        m = pattern.search(sentence[:2000])
        if not m:
            continue
        if len(sentence) > 240:  # keep the part around the version
            start = max(0, m.start() - 140)
            sentence = ("…" if start else "") + sentence[start : m.end() + 80].strip() + "…"
        stem = sentence.rstrip("…")
        if any(q.rstrip("…").startswith(stem) or stem.startswith(q.rstrip("…")) for q in out):
            continue  # the same sentence, quoted twice (e.g. from the title and the description)
        out.append(sentence)
        if len(out) >= MAX_STATED:
            break
    return out


def stated_fix(text: str | None) -> str | None:
    """The fix sentences of an official description, or None when it states no fixed version."""
    quotes = stated(text or "", _FIX_RE)
    return ("Stated by the official record: " + " ".join(quotes)) if quotes else None
