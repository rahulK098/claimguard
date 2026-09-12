"""Provider fallback chain.

`FallbackLLMClient` tries providers in order, catching `ProviderCallError`
and moving to the next, until one succeeds or every configured provider has
been tried. It implements the same `LLMClient` protocol as a single
provider, so it's a drop-in wherever one is expected (including as the
`inner` client `RecordingClient` wraps).

`build_default_chain` wires the chain automatically from whatever is
actually present in `.env`: the configured primary (`LLM_PROVIDER`) first,
then every other provider with credentials present in a fixed canonical
order, then local Ollama last (always eligible, no credentials required).
See docs/adr/0011-multi-provider-llm.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel

from claimguard.llm.client import LLMClient, LLMResult, ProviderCallError
from claimguard.llm.pricing import ModelRate, resolve_rate
from claimguard.llm.provider_settings import ProviderSettings
from claimguard.llm.providers.anthropic_client import AnthropicClient
from claimguard.llm.providers.gemini_client import GeminiClient
from claimguard.llm.providers.ollama_client import OllamaClient
from claimguard.llm.providers.openai_compatible import (
    AzureOpenAIClient,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)

T = TypeVar("T", bound=BaseModel)

# Fixed order for "every other configured provider" once the primary has had
# its turn. Ollama is handled separately in build_default_chain -- it's
# always appended last, unconditionally.
_CANONICAL_ORDER = ["azure", "anthropic", "openrouter", "groq", "gemini", "deepseek"]


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    error: str


class AllProvidersExhaustedError(Exception):
    """Raised when every provider in the chain failed. Phase 4 turns this
    into a typed LLMFailure(kind=PROVIDER_UNAVAILABLE) rather than crashing
    the graph -- see schemas.handoffs.LLMFailureKind."""

    def __init__(self, attempts: list[ProviderAttempt]) -> None:
        summary = "; ".join(f"{a.provider}: {a.error}" for a in attempts)
        super().__init__(f"every configured provider failed -- {summary}")
        self.attempts = attempts


class FallbackLLMClient:
    def __init__(self, providers: list[tuple[str, LLMClient]]) -> None:
        if not providers:
            raise ValueError("FallbackLLMClient requires at least one provider")
        self._providers = providers

    @property
    def provider_names(self) -> list[str]:
        return [name for name, _ in self._providers]

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        attempts: list[ProviderAttempt] = []
        for name, client in self._providers:
            try:
                return await client.parse(
                    node=node, system=system, user=user, output_model=output_model, effort=effort
                )
            except ProviderCallError as exc:
                attempts.append(ProviderAttempt(name, str(exc)))
                continue
        raise AllProvidersExhaustedError(attempts)

    async def aclose(self) -> None:
        for _, client in self._providers:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()


def _override_rate(input_rate: float | None, output_rate: float | None) -> ModelRate | None:
    if input_rate is None or output_rate is None:
        return None
    return ModelRate(input_rate, output_rate)


def _azure_rate(settings: ProviderSettings) -> ModelRate | None:
    override = _override_rate(settings.azure_input_usd_per_mtok, settings.azure_output_usd_per_mtok)
    return resolve_rate("azure", override)


def _groq_rate(settings: ProviderSettings) -> ModelRate | None:
    override = _override_rate(settings.groq_input_usd_per_mtok, settings.groq_output_usd_per_mtok)
    return resolve_rate("groq", override)


def _deepseek_rate(settings: ProviderSettings) -> ModelRate | None:
    override = _override_rate(
        settings.deepseek_input_usd_per_mtok, settings.deepseek_output_usd_per_mtok
    )
    return resolve_rate("deepseek", override)


def _openrouter_rate(settings: ProviderSettings) -> ModelRate | None:
    override = _override_rate(
        settings.openrouter_input_usd_per_mtok, settings.openrouter_output_usd_per_mtok
    )
    rate = resolve_rate("openrouter", override)
    if rate is None and settings.openrouter_model.endswith(":free"):
        # A :free-suffixed model is $0 by definition (OpenRouter's own
        # convention), independent of whether the operator configured a rate.
        rate = ModelRate(0.0, 0.0)
    return rate


def _build_provider(
    name: str, settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None
) -> LLMClient | None:
    if name == "azure":
        keys = [k for k in (settings.azure_openai_key, settings.azure_openai_key2) if k]
        if not keys or not settings.azure_openai_endpoint:
            return None
        return AzureOpenAIClient(
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
            keys=keys,
            rate=_azure_rate(settings),
            transport=transport,
        )
    if name == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    if name == "openrouter":
        if not settings.openrouter_api_key:
            return None
        return OpenAICompatibleClient(
            OpenAICompatibleConfig(
                provider_name="openrouter",
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://github.com/rahulK098/claimguard",
                    "X-Title": "ClaimGuard",
                },
                model=settings.openrouter_model,
                rate=_openrouter_rate(settings),
            ),
            transport=transport,
        )
    if name == "groq":
        if not settings.groq_api_key:
            return None
        return OpenAICompatibleClient(
            OpenAICompatibleConfig(
                provider_name="groq",
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                model=settings.groq_model,
                rate=_groq_rate(settings),
            ),
            transport=transport,
        )
    if name == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            rate=resolve_rate("gemini", None),
            transport=transport,
        )
    if name == "deepseek":
        if not settings.deepseek_api_key:
            return None
        return OpenAICompatibleClient(
            OpenAICompatibleConfig(
                provider_name="deepseek",
                url="https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                model=settings.deepseek_model,
                rate=_deepseek_rate(settings),
            ),
            transport=transport,
        )
    if name == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url, model=settings.ollama_model, transport=transport
        )
    return None


def build_default_chain(
    settings: ProviderSettings, *, transport: httpx.AsyncBaseTransport | None = None
) -> FallbackLLMClient:
    """The primary provider, then every other configured cloud provider, then Ollama last."""
    order = [settings.provider] + [p for p in _CANONICAL_ORDER if p != settings.provider]
    providers: list[tuple[str, LLMClient]] = []
    for name in order:
        client = _build_provider(name, settings, transport=transport)
        if client is not None:
            providers.append((name, client))
    # Ollama is always eligible and always last, even if it was already the
    # primary (in which case it's already first and shouldn't be duplicated).
    if settings.provider != "ollama":
        ollama = _build_provider("ollama", settings, transport=transport)
        assert ollama is not None
        providers.append(("ollama", ollama))
    if not providers:
        raise ValueError(
            "no LLM provider is configured -- set at least one provider's API key "
            "(e.g. AZURE_OPENAI_KEY + AZURE_OPENAI_ENDPOINT, or ANTHROPIC_API_KEY)"
        )
    return FallbackLLMClient(providers)
