"""OpenAI (or any OpenAI-compatible) Chat Completions + Embeddings."""

from typing import Any

from app.ai.providers._http import post_json
from app.ai.providers.base import Completion, ProviderError, Usage
from app.ingestion.http import HttpClient


class OpenAIChat:
    name = "openai"

    def __init__(self, http: HttpClient, api_key: str, model: str, base_url: str) -> None:
        self.http, self.model, self._key, self.base = http, model, api_key, base_url.rstrip("/")
        self._send_temperature = True  # reasoning models (o-series, gpt-5) only accept the default

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
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema},
            },
            "max_completion_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self._key}"}
        url = f"{self.base}/chat/completions"
        try:
            first = {**payload, "temperature": temperature} if self._send_temperature else payload
            data = await post_json(self.http, url, first, headers, "OpenAI")
        except ProviderError as exc:
            # 400 "Unsupported value: 'temperature' ... Only the default (1) value is supported."
            if not (self._send_temperature and exc.status == 400 and "temperature" in str(exc)):
                raise
            self._send_temperature = False  # remembered for this model
            data = await post_json(self.http, url, payload, headers, "OpenAI")
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
