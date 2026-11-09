"""Guards against unsupported claims in AI output.

A "claim token" is something checkable: numbers with decimals, versions, CVE/CWE ids, percentages, dates.
Any such token in generated text that does not appear in the source material is unsupported. Sentences
containing unsupported tokens are removed, and the tokens are reported.
"""

import re

TOKEN_RE = re.compile(
    r"\bCVE-\d{4}-\d{4,}\b|\bCWE-\d+\b|\bv?\d+(?:\.\d+)+(?:[-+][\w.]+)?\b|\b\d+(?:\.\d+)?%|\b\d{4}-\d{2}-\d{2}\b|\b\d{2,}\b"
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
REMEDIATION_RE = re.compile(r"\b(upgrade|update|patch|fixed in|apply|install|mitigat|workaround)\w*", re.I)


def _norm(t: str) -> str:
    return t.lower().lstrip("v")


def claim_tokens(text: str) -> set[str]:
    return {_norm(t) for t in TOKEN_RE.findall(text or "")}


def unsupported_tokens(generated: str, sources: str) -> list[str]:
    allowed = claim_tokens(sources)
    return sorted(t for t in claim_tokens(generated) if t not in allowed)


def strip_unsupported(generated: str, sources: str) -> tuple[str, list[str]]:
    """Drop sentences that contain claims not found in the sources."""
    if not generated:
        return generated, []
    bad = set(unsupported_tokens(generated, sources))
    if not bad:
        return generated, []
    kept = [s for s in SENTENCE_RE.split(generated) if not (claim_tokens(s) & bad)]
    return " ".join(kept).strip(), sorted(bad)


def filter_actions(
    actions: list[str], sources: str, has_trusted_remediation: bool
) -> tuple[list[str], list[str]]:
    """Recommended actions must be grounded. For vulnerabilities without official remediation, any
    patch/upgrade instruction is removed (we never invent a fix)."""
    kept, dropped = [], []
    for a in actions:
        if unsupported_tokens(a, sources):
            dropped.append(a)
        elif not has_trusted_remediation and REMEDIATION_RE.search(a):
            dropped.append(a)
        else:
            kept.append(a)
    return kept, dropped
