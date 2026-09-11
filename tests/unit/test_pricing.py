"""Pricing table and cost computation."""

import pytest

from claimguard.llm.pricing import PRICING, UnknownModelError, compute_cost_usd


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"])
def test_every_configured_model_is_priced(model: str) -> None:
    assert model in PRICING


def test_opus_5_cost_matches_published_rate() -> None:
    # 1M input + 1M output tokens at $5.00 / $25.00 per MTok.
    cost = compute_cost_usd("claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(30.00)


def test_partial_token_counts_scale_linearly() -> None:
    cost = compute_cost_usd("claude-opus-5", input_tokens=500_000, output_tokens=0)
    assert cost == pytest.approx(2.50)


def test_zero_tokens_cost_zero() -> None:
    assert compute_cost_usd("claude-sonnet-5", input_tokens=0, output_tokens=0) == 0.0


def test_unknown_model_raises() -> None:
    with pytest.raises(UnknownModelError):
        compute_cost_usd("claude-nonexistent-9", input_tokens=100, output_tokens=100)


def test_output_tokens_cost_more_than_input_tokens_for_every_model() -> None:
    for rate in PRICING.values():
        assert rate.output_usd_per_mtok > rate.input_usd_per_mtok
