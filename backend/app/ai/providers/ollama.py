"""Ollama local models: /api/chat with a JSON-schema `format`, and /api/embed."""

from typing import Any

from app.ai.providers._http import post_json
from app.ai.providers.base import Completion, Usage
from app.ingestion.http import HttpClient


class OllamaChat:
    name = "ollama"

    def __init__(self, http: HttpClient, model: str, base_url: str) -> None:
        self.http, self.model, self.base = http, model, base_url.rstrip("/")

    async def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        data = await post_json(
            self.http,
            f"{self.base}/api/chat",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": schema,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            {},
            "Ollama",
        )
        content = (data.get("message") or {}).get("content") or ""
        return Completion(content, Usage(data.get("prompt_eval_count", 0), data.get("eval_count", 0)))


class OllamaEmbeddings:
    name = "ollama"

    def __init__(self, http: HttpClient, model: str, base_url: str, dim: int) -> None:
        self.http, self.model, self.base, self.dim = http, model, base_url.rstrip("/"), dim

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        data = await post_json(
            self.http, f"{self.base}/api/embed", {"model": self.model, "input": texts}, {}, "Ollama"
        )
        return data.get("embeddings") or [], Usage(data.get("prompt_eval_count", 0), 0)
