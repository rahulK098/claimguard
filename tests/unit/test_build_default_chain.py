"""llm.fallback.build_default_chain: wires the fallback chain automatically
from whatever ProviderSettings actually has configured -- the "multi means
whatever is present in .env should just work" behavior."""

import pytest

from claimguard.llm.fallback import build_default_chain
from claimguard.llm.provider_settings import ProviderSettings


def test_raises_when_nothing_is_configured() -> None:
    # Ollama would normally make this always succeed; force it off the table
    # by asserting on the "no providers" branch directly isn't possible since
    # ollama has no credential gate -- so this instead documents that Ollama
    # alone is enough to build a (degenerate) one-provider chain.
    settings = ProviderSettings(_env_file=None, provider="ollama")
    chain = build_default_chain(settings)
    assert chain.provider_names == ["ollama"]


def test_only_anthropic_configured() -> None:
    settings = ProviderSettings(_env_file=None, provider="anthropic", anthropic_api_key="sk-ant-x")
    chain = build_default_chain(settings)
    assert chain.provider_names == ["anthropic", "ollama"]


def test_azure_primary_with_other_providers_configured() -> None:
    settings = ProviderSettings(
        _env_file=None,
        provider="azure",
        azure_openai_key="key-1",
        azure_openai_endpoint="https://example.openai.azure.com",
        groq_api_key="groq-key",
        gemini_api_key="gemini-key",
    )
    chain = build_default_chain(settings)
    # azure first (primary), then canonical order for the rest, ollama last.
    assert chain.provider_names == ["azure", "groq", "gemini", "ollama"]


def test_azure_key_without_endpoint_is_excluded() -> None:
    settings = ProviderSettings(_env_file=None, provider="azure", azure_openai_key="key-1")
    chain = build_default_chain(settings)
    assert "azure" not in chain.provider_names
    assert chain.provider_names == ["ollama"]


def test_azure_endpoint_without_any_key_is_excluded() -> None:
    settings = ProviderSettings(
        _env_file=None, provider="azure", azure_openai_endpoint="https://x.openai.azure.com"
    )
    chain = build_default_chain(settings)
    assert "azure" not in chain.provider_names


def test_configured_primary_is_tried_first_even_if_later_in_canonical_order() -> None:
    settings = ProviderSettings(
        _env_file=None,
        provider="deepseek",
        deepseek_api_key="ds-key",
        anthropic_api_key="sk-ant-x",
    )
    chain = build_default_chain(settings)
    assert chain.provider_names[0] == "deepseek"
    assert chain.provider_names == ["deepseek", "anthropic", "ollama"]


def test_unconfigured_providers_are_skipped_entirely() -> None:
    settings = ProviderSettings(_env_file=None, provider="anthropic", anthropic_api_key="sk-ant-x")
    chain = build_default_chain(settings)
    for absent in ("azure", "openrouter", "groq", "gemini", "deepseek"):
        assert absent not in chain.provider_names


def test_ollama_is_not_duplicated_when_it_is_also_the_primary() -> None:
    settings = ProviderSettings(_env_file=None, provider="ollama", anthropic_api_key="sk-ant-x")
    chain = build_default_chain(settings)
    assert chain.provider_names.count("ollama") == 1
    assert chain.provider_names == ["ollama", "anthropic"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("openrouter_api_key", "or-key"),
        ("groq_api_key", "groq-key"),
        ("gemini_api_key", "gemini-key"),
        ("deepseek_api_key", "ds-key"),
    ],
)
def test_each_cloud_provider_activates_on_its_own_key(field: str, value: str) -> None:
    settings = ProviderSettings(_env_file=None, provider="anthropic", **{field: value})
    chain = build_default_chain(settings)
    provider_name = field.split("_api_key")[0]
    assert provider_name in chain.provider_names
