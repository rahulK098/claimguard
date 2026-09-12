"""Every non-Anthropic provider adapter, against a mocked HTTP transport
(httpx.MockTransport) rather than a real network call -- exercises the real
request-building and response-parsing code, including the
native-structured-output-first / prompt-fallback-second behavior, with no
credentials and no network."""

from collections.abc import Callable

import httpx
import pytest

from claimguard.llm.client import ProviderCallError
from claimguard.llm.pricing import ModelRate
from claimguard.llm.providers.gemini_client import GeminiClient
from claimguard.llm.providers.ollama_client import OllamaClient
from claimguard.llm.providers.openai_compatible import (
    AzureOpenAIClient,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from claimguard.schemas.handoffs import ExtractorOutput

EXTRACTOR_JSON = (
    '{"claim_id": "CLM-1", "policy_number": "POL-1", "claimant_id": "CLT-1", '
    '"incident_description": "fender bender", "damage_category": "minor", '
    '"damage_estimate_usd": 1200, "extraction_confidence": "high", "missing_fields": []}'
)


def _openai_success_body(content: str = EXTRACTOR_JSON) -> dict[str, object]:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30},
    }


def counting_handler(
    responses: list[Callable[[httpx.Request], httpx.Response]],
) -> Callable[[httpx.Request], httpx.Response]:
    """Returns a MockTransport handler that yields each response in order,
    one per request, so tests can script "first attempt fails, second succeeds"."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[i](request)

    return handler


# --- OpenAICompatibleClient (also exercised via Groq/DeepSeek/OpenRouter configs) --


async def test_openai_compatible_succeeds_on_first_json_schema_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"json_schema" in request.content
        return httpx.Response(200, json=_openai_success_body())

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            provider_name="groq",
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer x"},
            model="llama-3.3-70b-versatile",
            rate=ModelRate(0.1, 0.2),
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.provider == "groq"
    assert result.parsed.claim_id == "CLM-1"
    assert result.cost_priced is True
    assert result.cost_usd == pytest.approx(50 / 1e6 * 0.1 + 30 / 1e6 * 0.2)
    await client.aclose()


async def test_openai_compatible_falls_back_when_json_schema_is_rejected() -> None:
    handler = counting_handler(
        [
            lambda r: httpx.Response(400, json={"error": "response_format not supported"}),
            lambda r: httpx.Response(200, json=_openai_success_body()),
        ]
    )
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            provider_name="deepseek",
            url="https://api.deepseek.com/chat/completions",
            headers={"Authorization": "Bearer x"},
            model="deepseek-chat",
        ),
        transport=httpx.MockTransport(handler),
    )
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.parsed.claim_id == "CLM-1"
    # Unpriced provider (deepseek has no default rate and no override here).
    assert result.cost_priced is False
    assert result.cost_usd == 0.0
    await client.aclose()


async def test_openai_compatible_raises_when_both_attempts_fail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            provider_name="groq",
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer x"},
            model="llama-3.3-70b-versatile",
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


async def test_openai_compatible_raises_on_unexpected_response_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            provider_name="groq",
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer x"},
            model="llama-3.3-70b-versatile",
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


async def test_openai_compatible_raises_when_content_is_not_valid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_success_body(content="I cannot help with that."))

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            provider_name="groq",
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer x"},
            model="llama-3.3-70b-versatile",
            try_json_schema=False,
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


# --- AzureOpenAIClient key rotation ------------------------------------------


async def test_azure_rotates_to_second_key_when_first_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("api-key") == "bad-key":
            return httpx.Response(401, json={"error": "unauthorized"})
        return httpx.Response(200, json=_openai_success_body())

    client = AzureOpenAIClient(
        endpoint="https://example.openai.azure.com",
        deployment="chat",
        api_version="2024-10-21",
        keys=["bad-key", "good-key"],
        rate=None,
        transport=httpx.MockTransport(handler),
    )
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.provider == "azure"
    assert result.parsed.claim_id == "CLM-1"
    await client.aclose()


async def test_azure_raises_when_every_key_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = AzureOpenAIClient(
        endpoint="https://example.openai.azure.com",
        deployment="chat",
        api_version="2024-10-21",
        keys=["bad-key-1", "bad-key-2"],
        rate=None,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


def test_azure_requires_at_least_one_key() -> None:
    with pytest.raises(ValueError, match="at least one API key"):
        AzureOpenAIClient(
            endpoint="https://x.openai.azure.com",
            deployment="chat",
            api_version="2024-10-21",
            keys=[],
            rate=None,
        )


async def test_azure_uses_deployment_not_model_field_in_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b'"model"' not in request.content  # Azure ignores model; deployment is in the URL
        assert "/openai/deployments/my-deployment/" in str(request.url)
        return httpx.Response(200, json=_openai_success_body())

    client = AzureOpenAIClient(
        endpoint="https://example.openai.azure.com",
        deployment="my-deployment",
        api_version="2024-10-21",
        keys=["key-1"],
        rate=None,
        transport=httpx.MockTransport(handler),
    )
    await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


# --- GeminiClient -----------------------------------------------------------


async def test_gemini_success_on_first_attempt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-goog-api-key") == "gemini-key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": EXTRACTOR_JSON}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 20},
            },
        )

    client = GeminiClient(
        api_key="gemini-key",
        model="gemini-2.5-flash",
        rate=ModelRate(0.30, 2.50),
        transport=httpx.MockTransport(handler),
    )
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.provider == "gemini"
    assert result.cost_priced is True
    await client.aclose()


async def test_gemini_falls_back_when_response_schema_is_rejected() -> None:
    handler = counting_handler(
        [
            lambda r: httpx.Response(400, json={"error": "invalid schema"}),
            lambda r: httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": EXTRACTOR_JSON}]}, "finishReason": "STOP"}
                    ],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
                },
            ),
        ]
    )
    client = GeminiClient(api_key="k", transport=httpx.MockTransport(handler))
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.parsed.claim_id == "CLM-1"
    await client.aclose()


async def test_gemini_raises_on_persistent_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = GeminiClient(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()


# --- OllamaClient -------------------------------------------------------------


async def test_ollama_success_with_schema_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": EXTRACTOR_JSON,
                "prompt_eval_count": 25,
                "eval_count": 15,
                "done_reason": "stop",
            },
        )

    client = OllamaClient(model="qwen2.5:3b", transport=httpx.MockTransport(handler))
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.provider == "ollama"
    assert result.cost_usd == 0.0
    assert result.cost_priced is True
    await client.aclose()


async def test_ollama_falls_back_to_basic_json_mode() -> None:
    handler = counting_handler(
        [
            lambda r: httpx.Response(400, text="unsupported format"),
            lambda r: httpx.Response(
                200, json={"response": EXTRACTOR_JSON, "prompt_eval_count": 5, "eval_count": 5}
            ),
        ]
    )
    client = OllamaClient(transport=httpx.MockTransport(handler))
    result = await client.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.parsed.claim_id == "CLM-1"
    await client.aclose()


async def test_ollama_raises_when_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OllamaClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await client.aclose()
