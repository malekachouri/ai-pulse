"""Builds the configured providers from settings (environment variables only)."""

from dataclasses import dataclass

from app.ai.providers.anthropic import AnthropicChat
from app.ai.providers.base import (
    EmbeddingProvider,
    MalformedOutputError,
    ProviderError,
    ProviderNotConfiguredError,
    StructuredLLM,
    Usage,
)
from app.ai.providers.ollama import OllamaChat, OllamaEmbeddings
from app.ai.providers.openai import OpenAIChat, OpenAIEmbeddings
from app.core.config import Settings
from app.ingestion.http import HttpClient

__all__ = [
    "AIProviders",
    "Embedder",
    "MalformedOutputError",
    "ProviderError",
    "ProviderNotConfiguredError",
    "StructuredLLM",
    "Usage",
    "build_providers",
]


class Embedder:
    """Wraps an embedding provider: batching, empty-text guard and dimension check against pgvector."""

    def __init__(self, inner: EmbeddingProvider, batch_size: int = 64) -> None:
        self.inner = inner
        self.batch_size = batch_size

    @property
    def provider(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        vectors: list[list[float]] = []
        usage = Usage()
        for i in range(0, len(texts), self.batch_size):
            batch = [t[:8000] or " " for t in texts[i : i + self.batch_size]]
            out, u = await self.inner.embed(batch)
            usage += u
            if len(out) != len(batch):
                raise ProviderError(f"{self.provider} returned {len(out)} embeddings for {len(batch)} inputs")
            for v in out:
                if len(v) != self.inner.dim:
                    raise ProviderError(
                        f"Embedding dimension {len(v)} != {self.inner.dim}. "
                        f"Use a {self.inner.dim}-dim model "
                        "(e.g. nomic-embed-text on Ollama; OpenAI text-embedding-3-* is requested at it)."
                    )
            vectors.extend(out)
        return vectors, usage


@dataclass
class AIProviders:
    llm: StructuredLLM | None
    embedder: Embedder | None
    http: HttpClient | None = None
    problems: tuple[str, ...] = ()

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()


def build_providers(settings: Settings, http: HttpClient | None = None) -> AIProviders:
    """Return whatever is configured. Missing pieces are reported in `problems`, never guessed."""
    from app.ai.providers._http import make_client

    problems: list[str] = []
    http = http or make_client(settings.llm_timeout_seconds)
    key = lambda s: s.get_secret_value() if s else None  # noqa: E731

    chat = None
    p = settings.llm_provider
    if p != "none":
        if not settings.llm_model:
            problems.append("LLM_MODEL is not set")
        elif p == "openai" and not key(settings.openai_api_key):
            problems.append("OPENAI_API_KEY is not set")
        elif p == "anthropic" and not key(settings.anthropic_api_key):
            problems.append("ANTHROPIC_API_KEY is not set")
        elif p == "openai":
            chat = OpenAIChat(
                http, key(settings.openai_api_key) or "", settings.llm_model, settings.openai_base_url
            )
        elif p == "anthropic":
            chat = AnthropicChat(
                http, key(settings.anthropic_api_key) or "", settings.llm_model, settings.anthropic_api_url
            )
        elif p == "ollama":
            chat = OllamaChat(http, settings.llm_model, settings.ollama_base_url)

    ep = settings.embedding_provider
    if ep == "auto":
        ep = p if p in ("openai", "ollama") else "none"
    inner = None
    if ep != "none":
        if not settings.embedding_model:
            problems.append("EMBEDDING_MODEL is not set")
        elif ep == "openai":
            if key(settings.openai_api_key):
                inner = OpenAIEmbeddings(
                    http,
                    key(settings.openai_api_key) or "",
                    settings.embedding_model,
                    settings.openai_base_url,
                    settings.embedding_dim,
                )
            else:
                problems.append("OPENAI_API_KEY is required for OpenAI embeddings")
        elif ep == "ollama":
            inner = OllamaEmbeddings(
                http, settings.embedding_model, settings.ollama_base_url, settings.embedding_dim
            )

    llm = (
        StructuredLLM(
            chat,
            max_tokens=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
            price_in=settings.llm_price_input_per_mtok,
            price_out=settings.llm_price_output_per_mtok,
        )
        if chat
        else None
    )
    return AIProviders(llm, Embedder(inner) if inner else None, http, tuple(problems))
