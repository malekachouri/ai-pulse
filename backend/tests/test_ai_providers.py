import json

import httpx
import pytest

from app.ai.prompts import ItemAnalysis, RagAnswer
from app.ai.providers import MalformedOutputError, ProviderError, StructuredLLM, build_providers
from app.ai.providers.anthropic import AnthropicChat
from app.ai.providers.base import extract_json
from app.ai.providers.ollama import OllamaChat, OllamaEmbeddings
from app.ai.providers.openai import OpenAIChat, OpenAIEmbeddings
from app.core.config import Settings
from tests.ai_fakes import ScriptedChat, analysis_reply
from tests.ingestion_helpers import MockHttp


def test_factory_reads_env_and_reports_problems():
    s = Settings(llm_provider="openai", llm_model=None)
    p = build_providers(s)
    assert (
        "LLM_MODEL is not set" in p.problems and "EMBEDDING_MODEL is not set" in p.problems and p.llm is None
    )
    s = Settings(llm_provider="openai", llm_model="m", openai_api_key=None)
    assert "OPENAI_API_KEY is not set" in build_providers(s).problems
    p = build_providers(Settings(llm_provider="anthropic", llm_model="claude-x", anthropic_api_key="k"))
    assert p.llm.provider == "anthropic" and p.llm.model == "claude-x"
    assert p.embedder is None  # Anthropic has no embeddings; nothing guessed
    p = build_providers(
        Settings(
            llm_provider="anthropic",
            llm_model="c",
            anthropic_api_key="k",
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
        )
    )
    assert p.embedder.provider == "ollama" and p.embedder.model == "nomic-embed-text"
    assert build_providers(Settings()).llm is None  # default: no provider


def test_extract_json_tolerates_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope it helps') == {"a": 2}
    with pytest.raises(json.JSONDecodeError):
        extract_json("no json here")


async def test_openai_wire_format_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert body["model"] == "my-model" and body["response_format"]["type"] == "json_schema"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"answer": "x [1]"})}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    mock = MockHttp({"https://api.openai.com/v1/chat/completions": handler})
    llm = StructuredLLM(
        OpenAIChat(mock.client(), "sk-test", "my-model", "https://api.openai.com/v1"),
        max_tokens=100,
        temperature=0,
        price_in=2.0,
        price_out=8.0,
    )
    r = await llm.complete_json("sys", "q", RagAnswer)
    assert r.data.answer == "x [1]" and (r.usage.input_tokens, r.usage.output_tokens) == (12, 3)
    assert r.cost_usd == round(12 / 1e6 * 2 + 3 / 1e6 * 8, 6) and r.provider == "openai"


async def test_openai_refusal_and_auth_error():
    mock = MockHttp(
        {
            "https://api.openai.com/v1/chat/completions": [
                httpx.Response(200, json={"choices": [{"message": {"refusal": "I can't"}}]}),
                httpx.Response(401, json={"error": {"message": "bad key"}}),
            ]
        }
    )
    chat = OpenAIChat(mock.client(), "k", "m", "https://api.openai.com/v1")
    with pytest.raises(ProviderError, match="refused"):
        await chat.complete("s", "u", schema={}, schema_name="X", max_tokens=1, temperature=0)
    with pytest.raises(ProviderError) as e:
        await chat.complete("s", "u", schema={}, schema_name="X", max_tokens=1, temperature=0)
    assert e.value.status == 401 and e.value.retryable is False


async def test_rate_limited_then_ok_is_retried():
    ok = httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": "a"}'}}], "usage": {}})
    mock = MockHttp({"https://api.openai.com/": [httpx.Response(429, headers={"Retry-After": "1"}), ok]})
    chat = OpenAIChat(mock.client(), "k", "m", "https://api.openai.com/v1")
    c = await chat.complete("s", "u", schema={}, schema_name="X", max_tokens=1, temperature=0)
    assert c.text and len(mock.requests) == 2


async def test_server_errors_exhaust_retries():
    mock = MockHttp({"https://api.openai.com/": httpx.Response(503)})
    chat = OpenAIChat(mock.client(max_attempts=2), "k", "m", "https://api.openai.com/v1")
    with pytest.raises(ProviderError) as e:
        await chat.complete("s", "u", schema={}, schema_name="X", max_tokens=1, temperature=0)
    assert e.value.retryable is True


async def test_anthropic_forced_tool_structured_output():
    def handler(request):
        body = json.loads(request.content)
        assert request.headers["x-api-key"] == "ak" and request.headers["anthropic-version"] == "2023-06-01"
        assert body["tool_choice"] == {"type": "tool", "name": "RagAnswer"}
        assert body["tools"][0]["input_schema"]["properties"]["answer"]
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "name": "RagAnswer",
                        "input": {"answer": "yes [1]", "confidence": "high"},
                    }
                ],
                "usage": {"input_tokens": 40, "output_tokens": 9},
            },
        )

    mock = MockHttp({"https://api.anthropic.com/v1/messages": handler})
    llm = StructuredLLM(
        AnthropicChat(mock.client(), "ak", "configured-model", "https://api.anthropic.com"),
        max_tokens=50,
        temperature=0,
    )
    r = await llm.complete_json("s", "u", RagAnswer)
    assert (
        r.data.confidence == "high" and r.usage.input_tokens == 40 and r.cost_usd is None
    )  # no prices configured


async def test_ollama_chat_and_embeddings():
    def chat(request):
        body = json.loads(request.content)
        assert body["stream"] is False and body["format"]["title"] == "RagAnswer"
        return httpx.Response(
            200,
            json={"message": {"content": '{"answer": "local [1]"}'}, "prompt_eval_count": 7, "eval_count": 2},
        )

    def embed(request):
        return httpx.Response(200, json={"embeddings": [[0.1] * 768, [0.2] * 768]})

    mock = MockHttp({"http://ollama:11434/api/chat": chat, "http://ollama:11434/api/embed": embed})
    llm = StructuredLLM(
        OllamaChat(mock.client(), "llama-local", "http://ollama:11434"), max_tokens=10, temperature=0
    )
    assert (await llm.complete_json("s", "u", RagAnswer)).data.answer == "local [1]"
    vecs, _ = await OllamaEmbeddings(mock.client(), "nomic-embed-text", "http://ollama:11434", 768).embed(
        ["a", "b"]
    )
    assert len(vecs) == 2 and len(vecs[0]) == 768


async def test_embedding_dimension_mismatch_is_an_error():
    from app.ai.providers import Embedder

    mock = MockHttp(
        {
            "https://api.openai.com/v1/embeddings": httpx.Response(
                200, json={"data": [{"index": 0, "embedding": [0.0] * 1536}]}
            )
        }
    )
    emb = Embedder(
        OpenAIEmbeddings(mock.client(), "k", "text-embedding-3-small", "https://api.openai.com/v1", 768)
    )
    with pytest.raises(ProviderError, match="dimension 1536"):
        await emb.embed(["x"])
    assert json.loads(mock.requests[0].content)["dimensions"] == 768


async def test_malformed_output_retried_with_feedback_then_fails():
    chat = ScriptedChat(["not json at all", json.dumps(analysis_reply())])
    llm = StructuredLLM(chat, max_tokens=10, temperature=0)
    r = await llm.complete_json("s", "u", ItemAnalysis)
    assert r.attempts == 2 and "not valid JSON" in chat.calls[1]["user"]
    assert r.usage.input_tokens == 200  # both attempts counted

    bad = ScriptedChat(['{"short_summary": 1}', '{"wrong": true}'])
    with pytest.raises(MalformedOutputError):
        await StructuredLLM(bad, max_tokens=10, temperature=0).complete_json("s", "u", ItemAnalysis)


async def test_schema_violations_rejected():
    too_long = analysis_reply(short_summary="x" * 500)
    chat = ScriptedChat([too_long, too_long])
    with pytest.raises(MalformedOutputError):
        await StructuredLLM(chat, max_tokens=10, temperature=0).complete_json("s", "u", ItemAnalysis)


async def test_openai_reasoning_model_without_temperature_support():
    """o-series / gpt-5 models reject a non-default temperature: retry once without it, then remember."""
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "temperature" in body:
            return httpx.Response(400, json={"error": {
                "message": "Unsupported value: 'temperature' does not support 0.2 with this model. "
                           "Only the default (1) value is supported.",
                "type": "invalid_request_error", "param": "temperature", "code": "unsupported_value"}})  # fmt: skip
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"answer": "ok"})}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 1}})  # fmt: skip

    mock = MockHttp({"https://api.openai.com/v1/chat/completions": handler})
    llm = StructuredLLM(OpenAIChat(mock.client(), "sk", "gpt-5-mini", "https://api.openai.com/v1"),
                        max_tokens=100, temperature=0.2)  # fmt: skip
    assert (await llm.complete_json("s", "q", RagAnswer)).data.answer == "ok"
    assert (await llm.complete_json("s", "q", RagAnswer)).data.answer == "ok"
    assert ["temperature" in b for b in bodies] == [True, False, False]


async def test_provider_errors_carry_the_api_explanation():
    mock = MockHttp({"https://api.openai.com/v1/chat/completions": httpx.Response(
        404, json={"error": {"message": "The model `gpt-nope` does not exist", "code": "model_not_found"}})})  # fmt: skip
    llm = StructuredLLM(OpenAIChat(mock.client(), "sk-secret", "gpt-nope", "https://api.openai.com/v1"),
                        max_tokens=100, temperature=0)  # fmt: skip
    with pytest.raises(ProviderError) as e:
        await llm.complete_json("s", "q", RagAnswer)
    assert "does not exist" in str(e.value) and "sk-secret" not in str(e.value)
