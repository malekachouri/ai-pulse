"""Deterministic stand-ins for LLM/embedding providers (no network, no keys)."""

import hashlib
import json
import math
from typing import Any

from app.ai.providers import AIProviders, Embedder, StructuredLLM
from app.ai.providers.base import Completion, ProviderError, Usage
from app.ai.text import tokens


class ScriptedChat:
    """Returns queued replies (str/dict/Exception) in order; records every prompt."""

    name = "fake"
    model = "fake-model"

    def __init__(self, replies: list[Any] | None = None, default: Any = None) -> None:
        self.replies = list(replies or [])
        self.default = default
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, system: str, user: str, *, schema, schema_name, max_tokens, temperature
    ) -> Completion:  # type: ignore[no-untyped-def]
        self.calls.append({"system": system, "user": user, "schema_name": schema_name})
        reply = self.replies.pop(0) if self.replies else self.default
        if callable(reply) and not isinstance(reply, type):
            reply = reply(user)
        if isinstance(reply, Exception):
            raise reply
        if reply is None:
            raise ProviderError("no scripted reply", retryable=False)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return Completion(text, Usage(100, 50))


class HashEmbeddings:
    """Bag-of-words hashed into 768 dims: texts sharing words are close in cosine space."""

    name = "fake-embed"
    model = "hash-768"
    dim = 768

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        self.calls += 1
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in tokens(t) or ["empty"]:
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0  # noqa: S324
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out, Usage(len(texts) * 10, 0)


def providers(chat: ScriptedChat | None = None, embed: bool = False) -> AIProviders:
    llm = StructuredLLM(chat, max_tokens=500, temperature=0, price_in=1.0, price_out=2.0) if chat else None
    return AIProviders(llm, Embedder(HashEmbeddings()) if embed else None)


def analysis_reply(**over: Any) -> dict[str, Any]:
    base = {
        "short_summary": "Kubernetes fixed a denial of service in ingress-nginx.",
        "detailed_explanation": "A user who can create an Ingress can disrupt the data plane.",
        "what_happened": "A security issue was disclosed in ingress-nginx.",
        "why_it_matters": "Clusters using ingress-nginx may be affected.",
        "who_is_affected": "Clusters running ingress-nginx.",
        "technical_impact": {
            "level": "medium",
            "description": "Denial of service of the ingress data plane.",
        },
        "recommended_actions": ["Review the vendor advisory."],
        "related_technologies": ["Kubernetes", "ingress-nginx"],
        "categories": ["kubernetes", "cybersecurity", "not-a-category"],
        "entities": [{"type": "technology", "name": "ingress-nginx"}],
        "learning_topics": ["Ingress controller security"],
    }
    base.update(over)
    return base
