"""Deterministic NLP: cleaning, language detection, tokenisation, keywords, entities. No LLM involved."""

import math
import re
import unicodedata
from collections import Counter

from app.ingestion.text import html_to_text

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_URL = re.compile(r"https?://\S+")
_CODE = re.compile(r"```.*?```", re.S)
_BOILER = re.compile(
    r"^(subscribe|sign up|share this|follow us|cookie|all rights reserved|©|read more|click here).*$",
    re.I | re.M,
)


def clean_text(text: str | None, limit: int = 12000) -> str:
    """Plain text suitable for prompts/embeddings: no HTML, markdown images, code blocks, boilerplate lines."""
    if not text:
        return ""
    t = html_to_text(text) or ""
    t = _CODE.sub(" ", t)
    t = _MD_IMAGE.sub(" ", t)
    t = _MD_LINK.sub(r"\1", t)
    t = _BOILER.sub("", t)
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:limit]


STOPWORDS: dict[str, set[str]] = {
    "en": set(
        "the a an and or of to in on for with is are was were be been by this that it as at from we our "
        "you your can will not have has new into than more about which their they its also how what".split()
    ),
    "fr": set(
        "le la les un une des et ou de du au aux en dans pour avec est sont été par ce cette il elle nous "
        "vous sur plus pas que qui se ses leur".split()
    ),
    "de": set(
        "der die das und oder ein eine zu im in mit ist sind war für von auf dem den nicht auch sich "
        "wir sie es bei".split()
    ),
    "es": set("el la los las un una y o de del en para con es son por que se su sus al como más".split()),
    "it": set("il lo la i gli le un una e o di del in per con è sono che si non al della".split()),
    "pt": set("o a os as um uma e ou de do da em para com é são por que se não no na".split()),
}
# A word starts with a letter and runs over letters, digits and + # . - ("c++", "node.js", "gpt-4o").
# Deliberately no required final character: "[...]*[a-z0-9+#]" made the engine backtrack through every
# run it could not end (quadratic on input such as "a" + "ÿ" * n, from collected text). Trailing "." and
# "-" are trimmed in Python instead, which keeps matching linear.
_WORD_RUN = re.compile(r"[a-zà-ÿ][a-zà-ÿ0-9+#.\-]*", re.I)


def words(text: str) -> list[str]:
    """Words of `text` in order (linear time), without trailing "." or "-"."""
    return [w for w in (m.rstrip(".-") for m in _WORD_RUN.findall(text)) if w]


def detect_language(text: str) -> str | None:
    """Script check for CJK/Cyrillic/Arabic, then stopword frequency for Latin languages. None if unsure."""
    if not text or len(text.strip()) < 20:
        return None
    sample = text[:3000]
    counts = Counter()
    for ch in sample:
        name = unicodedata.name(ch, "")
        if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
            counts["zh/ja"] += 1
        elif "HANGUL" in name:
            counts["ko"] += 1
        elif "CYRILLIC" in name:
            counts["ru"] += 1
        elif "ARABIC" in name:
            counts["ar"] += 1
    letters = sum(ch.isalpha() for ch in sample) or 1
    if counts:
        script, n = counts.most_common(1)[0]
        if n / letters > 0.3:
            if script == "zh/ja":
                return (
                    "ja"
                    if any(
                        "HIRAGANA" in unicodedata.name(c, "") or "KATAKANA" in unicodedata.name(c, "")
                        for c in sample
                    )
                    else "zh"
                )
            return script
    sample_words = [w.lower() for w in words(sample)]
    if len(sample_words) < 5:
        return None
    scores = {lang: sum(w in sw for w in sample_words) / len(sample_words) for lang, sw in STOPWORDS.items()}
    best, score = max(scores.items(), key=lambda kv: kv[1])
    return best if score >= 0.05 else None


def tokens(text: str) -> list[str]:
    sw = STOPWORDS["en"]
    return [w.lower() for w in words(text) if w.lower() not in sw and len(w) > 1]


# Technology lexicon: boosts and canonical spelling for keywords/entities.
TECH = {
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "containerd": "containerd",
    "helm": "Helm",
    "terraform": "Terraform",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "istio": "Istio",
    "argo cd": "Argo CD",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "jax": "JAX",
    "vllm": "vLLM",
    "ollama": "Ollama",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "llama_index": "LlamaIndex",
    "transformers": "Transformers",
    "hugging face": "Hugging Face",
    "pgvector": "pgvector",
    "postgresql": "PostgreSQL",
    "redis": "Redis",
    "rag": "RAG",
    "retrieval-augmented generation": "RAG",
    "mcp": "MCP",
    "llm": "LLM",
    "llms": "LLM",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepmind": "Google DeepMind",
    "mistral": "Mistral AI",
    "meta": "Meta",
    "microsoft": "Microsoft",
    "nvidia": "NVIDIA",
    "cuda": "CUDA",
    "linux": "Linux",
    "python": "Python",
    "rust": "Rust",
    "go": "Go",
    "java": "Java",
    "node.js": "Node.js",
    "nginx": "NGINX",
    "ingress-nginx": "ingress-nginx",
    "openssl": "OpenSSL",
    "github": "GitHub",
}
ORGS = {
    "OpenAI",
    "Anthropic",
    "Google DeepMind",
    "Google",
    "Mistral AI",
    "Meta",
    "Microsoft",
    "NVIDIA",
    "AWS",
    "Azure",
    "Google Cloud",
    "Hugging Face",
    "GitHub",
    "CISA",
    "NIST",
    "CNCF",
    "Docker",
}
MODEL_RE = re.compile(
    r"\b(GPT-?\d[\w.-]*|o\d(?:-mini|-pro)?|Claude(?: [\w.]+)?|Gemini(?: [\d.]+)?(?: (?:Pro|Flash|Ultra|Nano))?|"
    r"Llama[ -]?\d[\w.-]*|Mistral[ -][\w.-]+|Mixtral[\w.-]*|Qwen[\d.]*[\w.-]*|DeepSeek[-\w.]*|Phi-\d[\w.-]*|Gemma[ -]?\d?[\w.-]*)\b"
)
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b")
CWE_RE = re.compile(r"\bCWE-\d+\b")
VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?\b")
REPO_RE = re.compile(r"\b(?:github\.com/)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")


def extract_keywords(text: str, n: int = 10) -> list[str]:
    """TF-weighted unigrams + bigrams with a technology-lexicon boost. Deterministic and explainable."""
    toks = tokens(text)
    if not toks:
        return []
    grams = Counter(toks)
    grams.update(f"{a} {b}" for a, b in zip(toks, toks[1:], strict=False) if not re.search(r"\d", a + b))
    scored = {}
    for g, c in grams.items():
        if len(g) < 3 or g.replace(".", "").isdigit():
            continue
        # one-off phrases are noise: a bigram must repeat; a single word must repeat or be a known technology
        if (" " in g and c < 2) or (" " not in g and c < 2 and g not in TECH):
            continue
        boost = 2.0 if g in TECH else 1.0
        scored[g] = c * boost * (1.2 if " " in g else 1.0) * math.log(2 + len(g))
    out: list[str] = []
    for g, _ in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0])):
        label = TECH.get(g, g)
        if label.lower() not in (o.lower() for o in out) and not any(label.lower() in o.lower() for o in out):
            out.append(label)
        if len(out) >= n:
            break
    return out


def extract_entities(text: str) -> list[dict[str, str]]:
    """Rule-based entities with a `type`; every value literally appears in the text."""
    found: dict[tuple[str, str], None] = {}

    def add(kind: str, value: str) -> None:
        found.setdefault((kind, value.strip()), None)

    for m in CVE_RE.findall(text):
        add("cve", m)
    for m in CWE_RE.findall(text):
        add("cwe", m)
    for m in MODEL_RE.findall(text):
        if len(m) > 2:
            add("model", m)
    low = text.lower()
    for key, label in TECH.items():
        if re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", low):
            add("organization" if label in ORGS else "technology", label)
    for m in VERSION_RE.findall(text)[:10]:
        add("version", m)
    return [{"type": k, "value": v} for k, v in list(found)[:40]]
