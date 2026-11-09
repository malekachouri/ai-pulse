"""Default source catalog: official, machine-readable endpoints only.

Verified live (HTTP 200 with the expected format) on 2026-11-09 unless marked `live_check: False`.
Not included, on purpose:
* Anthropic, Mistral AI and Meta AI news pages - no official RSS/API exists (anthropic.com/news/rss.xml and
  mistral.ai/news/rss.xml return 404) and AI Pulse does not scrape HTML. Their releases are covered through
  their official Hugging Face organisations and GitHub repositories instead.
* GitHub "trending" - there is no API; `github_trending` ranks Search API results and computes star growth
  from AI Pulse's own daily snapshots.
"""

from typing import Any

S: list[dict[str, Any]] = []


def _src(
    slug: str,
    name: str,
    source_type: str,
    connector: str,
    url: str,
    default_item_type: str,
    *,
    homepage: str | None = None,
    reliability: float = 0.9,
    interval: int = 60,
    official: bool = True,
    enabled: bool = True,
    live_check: bool = True,
    **config: Any,
) -> None:
    S.append(
        {
            "slug": slug,
            "name": name,
            "source_type": source_type,
            "connector": connector,
            "url": url,
            "homepage_url": homepage,
            "default_item_type": default_item_type,
            "is_official": official,
            "reliability": reliability,
            "poll_interval_minutes": interval,
            "enabled": enabled,
            "config": config,
            "live_check": live_check,
        }
    )


# --- AI announcements --------------------------------------------------------------------------------
_src(
    "openai-news",
    "OpenAI News",
    "rss",
    "rss",
    "https://openai.com/news/rss.xml",
    "news",
    homepage="https://openai.com/news/",
    categories=["ai-models"],
)
_src(
    "google-deepmind-blog",
    "Google DeepMind Blog",
    "rss",
    "rss",
    "https://deepmind.google/blog/rss.xml",
    "news",
    homepage="https://deepmind.google/discover/blog/",
    categories=["ai-research"],
)
_src(
    "huggingface-blog",
    "Hugging Face Blog",
    "rss",
    "rss",
    "https://huggingface.co/blog/feed.xml",
    "news",
    homepage="https://huggingface.co/blog",
    interval=120,
    categories=["ai-tools"],
)
_src(
    "hf-official-models",
    "Official model uploads on Hugging Face (Meta, Mistral AI, Google, Microsoft, Qwen, DeepSeek)",
    "api",
    "hf_models",
    "https://huggingface.co/api/models",
    "model_release",
    homepage="https://huggingface.co/models",
    interval=180,
    authors={
        "meta-llama": "Meta",
        "mistralai": "Mistral AI",
        "google": "Google",
        "microsoft": "Microsoft",
        "Qwen": "Alibaba Qwen",
        "deepseek-ai": "DeepSeek",
    },
)
_src(
    "ai-labs-github-releases",
    "AI lab releases on GitHub (Meta Llama, Mistral, Anthropic SDK)",
    "github",
    "github_releases",
    "https://api.github.com",
    "news",
    interval=360,
    live_check=False,
    repos=[
        {"repo": "meta-llama/llama-models", "kind": "news", "categories": ["ai-models"]},
        {"repo": "mistralai/mistral-inference", "kind": "news", "categories": ["ai-models"]},
        {"repo": "anthropics/anthropic-sdk-python", "kind": "news", "categories": ["ai-tools"]},
    ],
)

# --- Research ----------------------------------------------------------------------------------------
_src(
    "arxiv-ai",
    "arXiv: cs.CL, cs.LG, cs.AI",
    "api",
    "arxiv",
    "https://export.arxiv.org/api/query",
    "research",
    homepage="https://arxiv.org",
    interval=360,
    query="cat:cs.CL OR cat:cs.LG OR cat:cs.AI",
)
_src(
    "hf-daily-papers",
    "Hugging Face Daily Papers",
    "api",
    "hf_daily_papers",
    "https://huggingface.co/api/daily_papers",
    "research",
    homepage="https://huggingface.co/papers",
    reliability=0.75,
    interval=360,
)

# --- GitHub ------------------------------------------------------------------------------------------
_src(
    "github-rising-ai",
    "GitHub rising AI repositories (search + star snapshots)",
    "github",
    "github_trending",
    "https://api.github.com",
    "github_repo",
    reliability=0.6,
    interval=1440,
    live_check=False,
    queries=["topic:llm", "topic:rag", "topic:ai-agents", "topic:llmops", "topic:mlops"],
    min_stars=300,
    categories=["ai-tools"],
)
_src(
    "github-rising-devops",
    "GitHub rising DevOps repositories (search + star snapshots)",
    "github",
    "github_trending",
    "https://api.github.com",
    "github_repo",
    reliability=0.6,
    interval=1440,
    live_check=False,
    queries=["topic:kubernetes", "topic:devops", "topic:observability"],
    min_stars=300,
    categories=["devops"],
)
_src(
    "github-releases-ai-frameworks",
    "AI framework releases (vLLM, Transformers, LangChain, Ollama, LlamaIndex, pgvector)",
    "github",
    "github_releases",
    "https://api.github.com",
    "tool",
    interval=360,
    live_check=False,
    repos=[
        {"repo": "vllm-project/vllm", "kind": "tool", "tool_name": "vLLM", "categories": ["llmops"]},
        {
            "repo": "huggingface/transformers",
            "kind": "tool",
            "tool_name": "Transformers",
            "categories": ["ai-tools"],
        },
        {
            "repo": "langchain-ai/langchain",
            "kind": "tool",
            "tool_name": "LangChain",
            "categories": ["ai-agents"],
        },
        {"repo": "ollama/ollama", "kind": "tool", "tool_name": "Ollama", "categories": ["llmops"]},
        {"repo": "run-llama/llama_index", "kind": "tool", "tool_name": "LlamaIndex", "categories": ["rag"]},
        {"repo": "pgvector/pgvector", "kind": "tool", "tool_name": "pgvector", "categories": ["rag"]},
    ],
)
_src(
    "github-releases-cloud-native",
    "Cloud-native releases (Kubernetes, Docker/Moby, containerd, Helm, CNCF projects)",
    "github",
    "github_releases",
    "https://api.github.com",
    "devops",
    interval=360,
    live_check=False,
    repos=[
        {"repo": "kubernetes/kubernetes", "categories": ["kubernetes"]},
        {"repo": "moby/moby", "categories": ["docker"]},
        {"repo": "docker/compose", "categories": ["docker"]},
        {"repo": "containerd/containerd", "categories": ["docker"]},
        {"repo": "helm/helm", "categories": ["kubernetes"]},
        {"repo": "prometheus/prometheus", "categories": ["devops"]},
        {"repo": "argoproj/argo-cd", "categories": ["devops"]},
        {"repo": "istio/istio", "categories": ["kubernetes"]},
        {"repo": "cilium/cilium", "categories": ["kubernetes"]},
    ],
)
_src(
    "github-issues-ai-frameworks",
    "Bug and security issues in popular AI frameworks and Kubernetes",
    "github",
    "github_issues",
    "https://api.github.com",
    "bug",
    reliability=0.6,
    interval=120,
    live_check=False,
    repos=[
        {"repo": "vllm-project/vllm", "categories": ["llmops"]},
        {"repo": "huggingface/transformers"},
        {"repo": "langchain-ai/langchain", "categories": ["ai-agents"]},
        {"repo": "ollama/ollama", "categories": ["llmops"]},
        {
            "repo": "kubernetes/kubernetes",
            "labels": "kind/bug,priority/critical-urgent",
            "categories": ["kubernetes"],
        },
    ],
)

# --- Security ----------------------------------------------------------------------------------------
_src(
    "nvd-cve",
    "NVD CVE API 2.0",
    "api",
    "nvd",
    "https://services.nvd.nist.gov/rest/json/cves/2.0",
    "vulnerability",
    homepage="https://nvd.nist.gov/",
    reliability=0.95,
    interval=120,
)
_src(
    "cisa-kev",
    "CISA Known Exploited Vulnerabilities",
    "api",
    "cisa_kev",
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
    "vulnerability",
    homepage="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
    reliability=0.95,
    interval=360,
)
_src(
    "kubernetes-cve-feed",
    "Kubernetes official CVE feed",
    "api",
    "kubernetes_cve_feed",
    "https://kubernetes.io/docs/reference/issues-security/official-cve-feed/index.json",
    "vulnerability",
    homepage="https://kubernetes.io/docs/reference/issues-security/official-cve-feed/",
    reliability=0.95,
    interval=360,
)

_src(
    "github-advisories",
    "GitHub Security Advisories (reviewed: pip, npm, Go, Maven)",
    "github",
    "github_advisories",
    "https://api.github.com/advisories",
    "vulnerability",
    homepage="https://github.com/advisories",
    reliability=0.9,
    interval=180,
    live_check=False,
    ecosystems=["pip", "npm", "go", "maven"],
)

# --- Cloud & provider status -------------------------------------------------------------------------
_src(
    "gcp-status",
    "Google Cloud Service Health",
    "status_page",
    "gcp_status",
    "https://status.cloud.google.com/incidents.json",
    "incident",
    homepage="https://status.cloud.google.com/",
    reliability=0.95,
    interval=10,
)
_src(
    "aws-health",
    "AWS Health Dashboard (public RSS)",
    "status_page",
    "aws_status_rss",
    "https://status.aws.amazon.com/rss/all.rss",
    "incident",
    homepage="https://health.aws.amazon.com/health/status",
    reliability=0.95,
    interval=10,
)
_src(
    "azure-status",
    "Azure status",
    "status_page",
    "azure_status_rss",
    "https://azure.status.microsoft/en-us/status/feed/",
    "incident",
    homepage="https://azure.status.microsoft/en-us/status/",
    reliability=0.95,
    interval=10,
)
_src(
    "github-status",
    "GitHub Status",
    "status_page",
    "statuspage",
    "https://www.githubstatus.com/api/v2/incidents.json",
    "incident",
    homepage="https://www.githubstatus.com/",
    reliability=0.95,
    interval=10,
    provider="GitHub",
)
_src(
    "openai-status",
    "OpenAI Status",
    "status_page",
    "statuspage",
    "https://status.openai.com/api/v2/incidents.json",
    "incident",
    homepage="https://status.openai.com/",
    reliability=0.95,
    interval=10,
    provider="OpenAI",
)
_src(
    "anthropic-status",
    "Anthropic / Claude Status",
    "status_page",
    "statuspage",
    "https://status.claude.com/api/v2/incidents.json",
    "incident",
    homepage="https://status.claude.com/",
    reliability=0.95,
    interval=10,
    provider="Anthropic",
    live_check=False,
)
_src(
    "docker-status",
    "Docker Status",
    "status_page",
    "statuspage",
    "https://www.dockerstatus.com/api/v2/incidents.json",
    "incident",
    homepage="https://www.dockerstatus.com/",
    reliability=0.95,
    interval=10,
    provider="Docker",
)

# --- DevOps & cloud announcements --------------------------------------------------------------------
_src(
    "kubernetes-blog",
    "Kubernetes Blog",
    "rss",
    "rss",
    "https://kubernetes.io/feed.xml",
    "devops",
    homepage="https://kubernetes.io/blog/",
    interval=360,
    item_type="devops",
    categories=["kubernetes"],
)
_src(
    "docker-blog",
    "Docker Blog",
    "rss",
    "rss",
    "https://www.docker.com/blog/feed/",
    "devops",
    homepage="https://www.docker.com/blog/",
    interval=360,
    item_type="devops",
    categories=["docker"],
)
_src(
    "cncf-blog",
    "CNCF Blog",
    "rss",
    "rss",
    "https://www.cncf.io/feed/",
    "devops",
    homepage="https://www.cncf.io/blog/",
    interval=360,
    item_type="devops",
    categories=["devops"],
)
_src(
    "aws-whats-new",
    "AWS What's New",
    "rss",
    "rss",
    "https://aws.amazon.com/about-aws/whats-new/recent/feed/",
    "devops",
    homepage="https://aws.amazon.com/new/",
    interval=180,
    item_type="devops",
    categories=["cloud"],
)
_src(
    "gcp-release-notes",
    "Google Cloud release notes",
    "rss",
    "rss",
    "https://docs.cloud.google.com/feeds/gcp-release-notes.xml",
    "devops",
    homepage="https://cloud.google.com/release-notes",
    interval=360,
    item_type="devops",
    categories=["cloud"],
    live_check=False,
)

DEFAULT_SOURCES = S
