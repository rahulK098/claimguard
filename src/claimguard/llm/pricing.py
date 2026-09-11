"""Per-model pricing and cost computation.

Rates are Anthropic first-party API list prices, USD per million tokens,
current as of 2026-06-24. Only the models this project is configured to use
are listed — add a row here before pointing ``CLAIMGUARD_MODEL`` at a new
one; an unlisted model raises rather than silently costing $0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRate:
    input_usd_per_mtok: float
    output_usd_per_mtok: float


PRICING: dict[str, ModelRate] = {
    "claude-opus-5": ModelRate(input_usd_per_mtok=5.00, output_usd_per_mtok=25.00),
    "claude-sonnet-5": ModelRate(input_usd_per_mtok=2.00, output_usd_per_mtok=10.00),
    "claude-haiku-4-5": ModelRate(input_usd_per_mtok=1.00, output_usd_per_mtok=5.00),
}


class UnknownModelError(KeyError):
    """Raised when computing cost for a model not in PRICING."""


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in USD for one call's usage. Raises UnknownModelError if unpriced."""
    if model not in PRICING:
        raise UnknownModelError(
            f"no pricing entry for model {model!r}; add one to claimguard.llm.pricing.PRICING"
        )
    rate = PRICING[model]
    return (
        input_tokens / 1_000_000 * rate.input_usd_per_mtok
        + output_tokens / 1_000_000 * rate.output_usd_per_mtok
    )
