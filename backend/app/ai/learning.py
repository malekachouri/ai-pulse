"""Curated, stable official documentation links. The LLM proposes *topics*; links only come from here."""

CATALOG: dict[str, list[tuple[str, str]]] = {
    "kubernetes": [
        ("Kubernetes documentation", "https://kubernetes.io/docs/home/"),
        ("Kubernetes security checklist", "https://kubernetes.io/docs/concepts/security/security-checklist/"),
    ],
    "docker": [
        ("Docker documentation", "https://docs.docker.com/"),
        ("Docker security", "https://docs.docker.com/engine/security/"),
    ],
    "cybersecurity": [
        ("CVSS v3.1 specification (FIRST)", "https://www.first.org/cvss/v3.1/specification-document"),
        (
            "CISA Known Exploited Vulnerabilities",
            "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        ),
        ("OWASP Top 10", "https://owasp.org/www-project-top-ten/"),
    ],
    "rag": [
        ("Hugging Face: Advanced RAG cookbook", "https://huggingface.co/learn/cookbook/advanced_rag"),
        ("pgvector README", "https://github.com/pgvector/pgvector"),
    ],
    "ai-models": [("Hugging Face Hub documentation", "https://huggingface.co/docs/hub/index")],
    "ai-research": [("arXiv help: finding papers", "https://info.arxiv.org/help/index.html")],
    "ai-agents": [("Model Context Protocol", "https://modelcontextprotocol.io/")],
    "llmops": [
        ("vLLM documentation", "https://docs.vllm.ai/"),
        ("Ollama documentation", "https://github.com/ollama/ollama/tree/main/docs"),
    ],
    "mlops": [("MLflow documentation", "https://mlflow.org/docs/latest/index.html")],
    "cloud": [
        ("AWS Well-Architected Framework", "https://aws.amazon.com/architecture/well-architected/"),
        ("Google Cloud Architecture Center", "https://cloud.google.com/architecture"),
    ],
    "devops": [
        ("CNCF Landscape", "https://landscape.cncf.io/"),
        ("Prometheus documentation", "https://prometheus.io/docs/"),
    ],
    "infrastructure-failures": [
        ("Google SRE book: Postmortem culture", "https://sre.google/sre-book/postmortem-culture/")
    ],
    "bugs": [
        (
            "GitHub Docs: about issues",
            "https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues",
        )
    ],
    "software-engineering": [("Google SRE books", "https://sre.google/books/")],
    "ai-tools": [("Hugging Face Transformers docs", "https://huggingface.co/docs/transformers/index")],
}


def resources_for(categories: list[str], topics: list[str], limit: int = 4) -> list[dict[str, str | None]]:
    """Topics are AI-suggested (labelled as such); links are curated. Never an LLM-generated URL."""
    out: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for c in categories:
        for title, url in CATALOG.get(c, []):
            if url not in seen:
                seen.add(url)
                out.append({"title": title, "url": url, "source": "curated"})
    for t in topics[:3]:
        out.append({"title": t, "url": None, "source": "ai-suggested topic"})
    return out[: limit + 3]
