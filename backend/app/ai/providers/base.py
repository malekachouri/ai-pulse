"""LLM provider abstraction.

Providers only move bytes: build the request, call the API, return text + token usage. The shared
`StructuredLLM.complete_json` turns that into a validated Pydantic object, retrying once with the
validation error when the model returns malformed or schema-violating JSON.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger

log = get_logger(__name__)


class ProviderError(Exception):
    """API/transport failure. `retryable` tells callers whether trying later can help."""

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class ProviderNotConfiguredError(ProviderError):
    pass


class MalformedOutputError(ProviderError):
    def __init__(self, message: str, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __iadd__(self, other: Usage) -> Usage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        return self


@dataclass
class Completion:
    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass
class StructuredResult[T: BaseModel]:
    data: T
    usage: Usage
    provider: str
    model: str
    cost_usd: float | None
    attempts: int


class ChatProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        system: str,
        user: str,
        *,
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int,
        temperature: float,
    ) -> Completion: ...


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dim: int

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]: ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def extract_json(text: str) -> Any:
    """Parse JSON from model output, tolerating code fences or prose around a single object."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()


class StructuredLLM:
    def __init__(
        self,
        chat: ChatProvider,
        *,
        max_tokens: int,
        temperature: float,
        price_in: float | None = None,
        price_out: float | None = None,
    ) -> None:
        self.chat = chat
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.price_in = price_in
        self.price_out = price_out

    @property
    def provider(self) -> str:
        return self.chat.name

    @property
    def model(self) -> str:
        return self.chat.model

    def cost(self, usage: Usage) -> float | None:
        if self.price_in is None or self.price_out is None:
            return None
        return round(usage.input_tokens / 1e6 * self.price_in + usage.output_tokens / 1e6 * self.price_out, 6)

    async def complete_json[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> StructuredResult[T]:
        total = Usage()
        prompt = user
        last_error = ""
        raw = ""
        for attempt in (1, 2):
            completion = await self.chat.complete(
                system,
                prompt,
                schema=json_schema(schema),
                schema_name=schema.__name__,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            total += completion.usage
            raw = completion.text
            try:
                data = schema.model_validate(extract_json(raw))
                return StructuredResult(data, total, self.provider, self.model, self.cost(total), attempt)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = str(exc)[:800]
                log.warning(
                    "llm_malformed_output", provider=self.provider, attempt=attempt, error=last_error[:200]
                )
                prompt = (
                    f"{user}\n\nYour previous reply was not valid JSON for the required schema.\n"
                    f"Error: {last_error}\nReply again with ONLY a JSON object matching the schema."
                )
        raise MalformedOutputError(
            f"Model output did not match {schema.__name__}: {last_error}", raw=raw[:2000]
        )
