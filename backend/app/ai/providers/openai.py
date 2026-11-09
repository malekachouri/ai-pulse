"""OpenAI (or any OpenAI-compatible) Chat Completions + Embeddings."""

from typing import Any

from app.ai.providers._http import post_json
from app.ai.providers.base import Completion, ProviderError, Usage
from app.ingestion.http import HttpClient


class OpenAIChat:
    name = "openai"

    def __init__(self, http: HttpClient, api_key: str, model: str, base_url: str) -> None:
        self.http, self.model, self._key, self.base = http, model, api_key, base_url.rstrip("/")

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
            f"{self.base}/chat/completions",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema},
                },
                "max_completion_tokens": max_tokens,
                "temperature": temperature,
            },
            {"Authorization": f"Bearer {self._key}"},
            "OpenAI",
        )
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise ProviderError(f"OpenAI refused: {message['refusal'][:200]}")
        u = data.get("usage") or {}
        return Completion(
            message.get("content") or "", Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        )


class OpenAIEmbeddings:
    name = "openai"

    def __init__(self, http: HttpClient, api_key: str, model: str, base_url: str, dim: int) -> None:
        self.http, self.model, self._key, self.base, self.dim = (
            http,
            model,
            api_key,
            base_url.rstrip("/"),
            dim,
        )

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        data = await post_json(
            self.http,
            f"{self.base}/embeddings",
            {"model": self.model, "input": texts, "dimensions": self.dim},
            {"Authorization": f"Bearer {self._key}"},
            "OpenAI",
        )
        rows = sorted(data.get("data") or [], key=lambda r: r.get("index", 0))
        vectors = [r["embedding"] for r in rows]
        u = data.get("usage") or {}
        return vectors, Usage(u.get("prompt_tokens", 0), 0)
