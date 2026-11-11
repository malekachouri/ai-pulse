"""Explainable AI Pulse importance score (0-100). NOT a CVSS score.

score = 100 × Σ(weight_i × factor_i) / Σ(weight_i) over the factors that apply to the item.
Each factor is in [0, 1] and returned with its weight and a plain-language reason.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.enums import ItemType, Severity, VerificationStatus

VERSION = "importance-v1"
WEIGHTS = {
    "source_reliability": 0.20,
    "severity": 0.25,
    "recency": 0.15,
    "technical_impact": 0.15,
    "exploitation": 0.15,
    "verification": 0.10,
}
SEVERITY_VALUE = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.75,
    Severity.MEDIUM: 0.5,
    Severity.LOW: 0.25,
    Severity.INFO: 0.1,
}
# Baseline "severity" for items that have none, by type (how consequential the kind of item usually is).
TYPE_BASELINE = {
    ItemType.MODEL_RELEASE: 0.55,
    ItemType.INCIDENT: 0.5,
    ItemType.TOOL: 0.4,
    ItemType.RESEARCH: 0.35,
    ItemType.NEWS: 0.35,
    ItemType.DEVOPS: 0.35,
    ItemType.GITHUB_REPO: 0.3,
    ItemType.GITHUB_ISSUE: 0.3,
    ItemType.BUG: 0.3,
    ItemType.VULNERABILITY: 0.3,
}
IMPACT_VALUE = {"high": 1.0, "medium": 0.6, "low": 0.3, "none": 0.0}
HALF_LIFE_HOURS = 72.0


@dataclass
class Factor:
    name: str
    value: float
    weight: float
    reason: str


def score_item(
    *,
    item_type: ItemType,
    reliability: float,
    severity: Severity | None,
    severity_basis: str | None,
    published_at: datetime | None,
    collected_at: datetime,
    verification: VerificationStatus,
    now: datetime,
    known_exploited: bool | None = None,
    impact_level: str | None = None,
    incident_active: bool | None = None,
) -> dict[str, Any]:
    factors: list[Factor] = [
        Factor(
            "source_reliability",
            round(reliability, 3),
            WEIGHTS["source_reliability"],
            f"Source reliability {reliability:.2f}",
        ),
    ]
    if severity in SEVERITY_VALUE:
        factors.append(
            Factor(
                "severity",
                SEVERITY_VALUE[severity],
                WEIGHTS["severity"],
                f"{severity.value} ({severity_basis or 'documented basis'})",
            )
        )
    else:
        base = TYPE_BASELINE.get(item_type, 0.3)
        factors.append(
            Factor("severity", base, WEIGHTS["severity"], f"No official severity; {item_type.value} baseline")
        )
    when = published_at or collected_at
    age_h = max(0.0, (now - when).total_seconds() / 3600)
    recency = math.pow(0.5, age_h / HALF_LIFE_HOURS)
    factors.append(
        Factor("recency", round(recency, 3), WEIGHTS["recency"], f"{age_h:.0f} h old (half-life 72 h)")
    )
    if impact_level in IMPACT_VALUE:
        factors.append(
            Factor(
                "technical_impact",
                IMPACT_VALUE[impact_level],
                WEIGHTS["technical_impact"],
                f"AI-assessed technical impact: {impact_level}",
            )
        )
    elif incident_active is not None:
        factors.append(
            Factor(
                "technical_impact",
                1.0 if incident_active else 0.3,
                WEIGHTS["technical_impact"],
                "Incident currently active per provider" if incident_active else "Incident not active",
            )
        )
    if item_type == ItemType.VULNERABILITY:
        exploited = bool(known_exploited)
        factors.append(
            Factor(
                "exploitation",
                1.0 if exploited else 0.0,
                WEIGHTS["exploitation"],
                "Known exploited (CISA KEV)" if exploited else "No known exploitation reported",
            )
        )
    ver = {
        VerificationStatus.OFFICIAL: 1.0,
        VerificationStatus.VERIFIED: 0.9,
        VerificationStatus.UNVERIFIED: 0.5,
        VerificationStatus.DISPUTED: 0.2,
    }[verification]
    factors.append(
        Factor("verification", ver, WEIGHTS["verification"], f"Verification: {verification.value}")
    )

    total_w = sum(f.weight for f in factors)
    score = round(100 * sum(f.weight * f.value for f in factors) / total_w, 1)
    return {
        "score": score,
        "version": VERSION,
        "label": "AI Pulse importance (0-100). Not an official CVSS score.",
        "factors": [
            {
                "name": f.name,
                "value": f.value,
                "weight": round(f.weight / total_w, 3),
                "contribution": round(100 * f.weight * f.value / total_w, 1),
                "reason": f.reason,
            }
            for f in factors
        ],
        "excluded": sorted(set(WEIGHTS) - {f.name for f in factors}),
    }


# User interests (preferences) -> the item categories they cover.
INTEREST_CATEGORIES: dict[str, set[str]] = {
    "ai-engineering": {"ai-tools", "llmops", "mlops"},
    "generative-ai": {"ai-models", "ai-research"},
    "rag": {"rag"},
    "ai-agents": {"ai-agents"},
    "llmops": {"llmops"},
    "devops": {"devops"},
    "cloud": {"cloud"},
    "kubernetes": {"kubernetes"},
    "cybersecurity": {"cybersecurity"},
    "software-engineering": {"software-engineering", "bugs"},
}


def personalize(
    base: float, *, categories: list[str], text: str, interests: list[str], followed: list[str]
) -> tuple[float, list[str]]:
    """Up to +15 points for matching the user's interests / followed technologies (explained)."""
    reasons: list[str] = []
    bonus = 0.0
    hits = [i for i in interests if INTEREST_CATEGORIES.get(i, set()) & set(categories)]
    if hits:
        bonus += min(10.0, 5.0 * len(hits))
        reasons.append(f"Matches your interests: {', '.join(hits)}")
    low = text.lower()
    follows = [f for f in followed if f and f.lower() in low]
    if follows:
        bonus += min(10.0, 5.0 * len(follows))
        reasons.append(f"Mentions what you follow: {', '.join(follows[:3])}")
    return round(min(100.0, base + min(15.0, bonus)), 1), reasons
