"""Anthropic Messages API. Structured output is obtained by forcing a single tool whose input schema is the
target JSON schema. Anthropic has no embeddings endpoint - pair it with an OpenAI or Ollama embedder."""

import json
from typing import Any

from app.ai.providers._http import post_json
from app.ai.providers.base import Completion, ProviderError, Usage
from app.ingestion.http import HttpClient

API_VERSION = "2023-06-01"


class AnthropicChat:
    name = "anthropic"

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
            f"{self.base}/v1/messages",
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "tools": [{"name": schema_name, "description": "Return the result.", "input_schema": schema}],
                "tool_choice": {"type": "tool", "name": schema_name},
            },
            {"x-api-key": self._key, "anthropic-version": API_VERSION},
            "Anthropic",
        )
        u = data.get("usage") or {}
        usage = Usage(u.get("input_tokens", 0), u.get("output_tokens", 0))
        for block in data.get("content") or []:
            if block.get("type") == "tool_use":
                return Completion(json.dumps(block.get("input") or {}), usage)
        text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
        if data.get("stop_reason") == "refusal":
            raise ProviderError("Anthropic declined the request")
        return Completion(text, usage)
