"""Deterministic keyword categorisation (AI classification is layered on top in the AI engine phase).

Rules only add categories that are evident from the source's own text; the source's configured
categories are always included so every record has at least one category.
"""

import re

RULES: dict[str, list[str]] = {
    "kubernetes": [
        r"\bkubernetes\b",
        r"\bk8s\b",
        r"\bkubectl\b",
        r"\bhelm\b",
        r"\bingress-nginx\b",
        r"\betcd\b",
    ],
    "docker": [r"\bdocker\b", r"\bcontainerd\b", r"\bmoby\b", r"\bdockerfile\b"],
    "rag": [
        r"\brag\b",
        r"retrieval[- ]augmented",
        r"\bvector (?:db|database|store|search)\b",
        r"\bembedding",
    ],
    "ai-agents": [r"\bagents?\b", r"\bagentic\b", r"\btool[- ]use\b", r"\bmcp\b"],
    "llmops": [r"\bllmops\b", r"\binference server", r"\bvllm\b", r"\bserving\b", r"\bevals?\b"],
    "mlops": [r"\bmlops\b", r"\bmlflow\b", r"\bkubeflow\b", r"\bfeature store\b"],
    "ai-models": [
        r"\bllm\b",
        r"\blanguage model",
        r"\bgpt-?\d",
        r"\bgemini\b",
        r"\bllama\b",
        r"\bmistral\b",
        r"\bclaude\b",
        r"\bopen[- ]weights?\b",
    ],
    "cybersecurity": [
        r"\bcve-\d{4}-\d+",
        r"\bvulnerab",
        r"\bexploit",
        r"\bsecurity (?:advisory|issue|fix)\b",
    ],
    "cloud": [r"\baws\b", r"\bamazon web services\b", r"\bazure\b", r"\bgoogle cloud\b", r"\bgcp\b"],
    "devops": [r"\bci/cd\b", r"\bterraform\b", r"\bgitops\b", r"\bargo ?cd\b", r"\bprometheus\b"],
}
_COMPILED = {slug: [re.compile(p, re.I) for p in pats] for slug, pats in RULES.items()}


def classify(text: str, defaults: list[str]) -> list[str]:
    out = list(dict.fromkeys(defaults))
    for slug, patterns in _COMPILED.items():
        if slug not in out and any(p.search(text) for p in patterns):
            out.append(slug)
    return out
