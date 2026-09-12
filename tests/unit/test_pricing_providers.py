"""llm.pricing's provider-generic cost path (resolve_rate, compute_cost_usd_or_zero,
PROVIDER_DEFAULT_RATES) -- distinct from the strict, Anthropic-only path
already covered by test_pricing.py."""

from claimguard.llm.pricing import (
    PROVIDER_DEFAULT_RATES,
    ModelRate,
    compute_cost_usd_or_zero,
    resolve_rate,
)


def test_gemini_has_a_verified_default_rate() -> None:
    assert PROVIDER_DEFAULT_RATES["gemini"] == ModelRate(0.30, 2.50)


def test_ollama_default_rate_is_zero_and_priced() -> None:
    rate = PROVIDER_DEFAULT_RATES["ollama"]
    assert rate == ModelRate(0.0, 0.0)


def test_azure_groq_deepseek_openrouter_have_no_default_rate() -> None:
    for provider in ("azure", "groq", "deepseek", "openrouter"):
        assert PROVIDER_DEFAULT_RATES[provider] is None


def test_resolve_rate_prefers_override_over_default() -> None:
    override = ModelRate(9.99, 19.99)
    assert resolve_rate("gemini", override) == override


def test_resolve_rate_falls_back_to_default_when_no_override() -> None:
    assert resolve_rate("gemini", None) == PROVIDER_DEFAULT_RATES["gemini"]


def test_resolve_rate_returns_none_for_unpriced_provider_with_no_override() -> None:
    assert resolve_rate("azure", None) is None


def test_compute_cost_usd_or_zero_with_a_rate() -> None:
    cost, priced = compute_cost_usd_or_zero(ModelRate(1.0, 2.0), 1_000_000, 1_000_000)
    assert cost == 3.0
    assert priced is True


def test_compute_cost_usd_or_zero_without_a_rate_is_unpriced_not_free() -> None:
    cost, priced = compute_cost_usd_or_zero(None, 1_000_000, 1_000_000)
    assert cost == 0.0
    assert priced is False
