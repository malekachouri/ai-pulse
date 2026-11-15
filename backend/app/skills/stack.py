"""Which technologies of AI Pulse an entry mentions: explainable keyword matches, shown as "Fits AI Pulse"."""

import re

# tag -> words that name it (whole words, case-insensitive). Keep in sync with docs/SKILLS.md.
STACK: dict[str, tuple[str, ...]] = {
    "postgresql": ("postgres", "postgresql", "pgvector", "psql"),
    "redis": ("redis",),
    "docker": ("docker", "dockerfile", "docker compose", "container", "containers"),
    "kubernetes": ("kubernetes", "k8s", "helm", "kubectl"),
    "github": ("github", "pull request", "pull requests", "github actions"),
    "security": ("security", "vulnerability", "vulnerabilities", "cve", "owasp", "sast", "secrets scanning"),
    "python": ("python", "pytest", "fastapi", "sqlalchemy", "alembic", "celery"),
    "typescript": ("typescript", "next.js", "nextjs", "react", "node.js", "nodejs", "vitest"),
    "ollama": ("ollama", "local llm", "local model", "local models"),
    "observability": ("prometheus", "grafana", "observability", "monitoring", "alerting"),
    "testing": ("playwright", "end-to-end", "e2e", "accessibility", "axe-core", "test automation"),
}

_PATTERNS = {
    tag: re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in words) + r")(?![\w-])", re.IGNORECASE)
    for tag, words in STACK.items()
}


def stack_tags(*texts: str | None) -> list[str]:
    """Tags of the AI Pulse technologies named in the texts, in the order of STACK."""
    text = " ".join(t for t in texts if t)[:20_000]
    return [tag for tag, pattern in _PATTERNS.items() if pattern.search(text)]
