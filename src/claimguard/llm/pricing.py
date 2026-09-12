"""Per-model and per-provider pricing and cost computation.

Two different cost paths, deliberately:

- **Anthropic models** (`PRICING`, `compute_cost_usd`): a small, fully
  curated table of Anthropic's own published list prices. An unpriced
  model *raises* -- a typo'd `CLAIMGUARD_MODEL` should fail loudly, not
  silently cost $0 and quietly break the budget ceiling's guarantee.
- **Every other provider** (`PROVIDER_DEFAULT_RATES`, `resolve_rate`,
  `compute_cost_usd_or_zero`): pricing here is genuinely not a single knowable
  fact the way Anthropic's list price is. Azure OpenAI pricing is
  contract/region/deployment-specific; Groq and DeepSeek's current rates
  could not be confidently verified at the time this was written (their
  published pricing pages and model lineups were in flux); OpenRouter's
  rate depends entirely on which model the operator points it at. Rather
  than hardcode numbers that might already be wrong, these are
  operator-configurable (`ProviderSettings`) with honest defaults: a
  verified rate where one exists (Gemini), a real $0 where that's actually
  correct (Ollama is local; OpenRouter `:free` models are $0 by definition),
  and `None` -- tracked as `cost_priced=False` on the result -- everywhere
  else, so the budget ceiling (Phase 4) can tell "$0.00, actually free" apart
  from "$0.00, unknown, don't trust this number" instead of conflating them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRate:
    input_usd_per_mtok: float
    output_usd_per_mtok: float


# Anthropic first-party API list prices, USD per million tokens, current as
# of 2026-06-24. Only the models this project is configured to use are
# listed -- add a row here before pointing CLAIMGUARD_MODEL at a new one.
PRICING: dict[str, ModelRate] = {
    "claude-opus-5": ModelRate(input_usd_per_mtok=5.00, output_usd_per_mtok=25.00),
    "claude-sonnet-5": ModelRate(input_usd_per_mtok=2.00, output_usd_per_mtok=10.00),
    "claude-haiku-4-5": ModelRate(input_usd_per_mtok=1.00, output_usd_per_mtok=5.00),
}


class UnknownModelError(KeyError):
    """Raised when computing Anthropic cost for a model not in PRICING."""


def compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in USD for one Anthropic call's usage. Raises if unpriced."""
    if model not in PRICING:
        raise UnknownModelError(
            f"no pricing entry for model {model!r}; add one to claimguard.llm.pricing.PRICING"
        )
    rate = PRICING[model]
    return (
        input_tokens / 1_000_000 * rate.input_usd_per_mtok
        + output_tokens / 1_000_000 * rate.output_usd_per_mtok
    )


# Verified or structurally-known default rates for non-Anthropic providers.
# `None` means "genuinely not a fixed fact -- the operator must configure a
# rate via ProviderSettings, or this provider's calls are tracked as unpriced."
PROVIDER_DEFAULT_RATES: dict[str, ModelRate | None] = {
    # ai.google.dev/gemini-api/docs/pricing, gemini-2.5-flash, verified 2026-09-12.
    "gemini": ModelRate(input_usd_per_mtok=0.30, output_usd_per_mtok=2.50),
    # Local inference -- genuinely $0 in this project's API-cost ledger. This
    # does not capture real compute/electricity cost; it states plainly that
    # this project doesn't meter it.
    "ollama": ModelRate(input_usd_per_mtok=0.0, output_usd_per_mtok=0.0),
    # Contract/region/deployment-specific -- no single public number exists.
    "azure": None,
    # Rate depends entirely on the operator's chosen model; `:free`-suffixed
    # OpenRouter models are $0 by definition (handled in llm.fallback), any
    # other model needs an operator-configured rate.
    "openrouter": None,
    # Could not be confidently verified at implementation time (pricing page
    # unreachable / model lineup uncertain). Configure via ProviderSettings.
    "groq": None,
    "deepseek": None,
}


def resolve_rate(provider: str, override: ModelRate | None) -> ModelRate | None:
    """An operator-supplied override always wins; otherwise the provider default."""
    return override if override is not None else PROVIDER_DEFAULT_RATES.get(provider)


def compute_cost_usd_or_zero(
    rate: ModelRate | None, input_tokens: int, output_tokens: int
) -> tuple[float, bool]:
    """Cost for a non-Anthropic call. Returns (cost_usd, priced).

    `priced=False` means `rate` was None -- the returned 0.0 is a
    placeholder, not a claim that the call was actually free.
    """
    if rate is None:
        return 0.0, False
    cost = (
        input_tokens / 1_000_000 * rate.input_usd_per_mtok
        + output_tokens / 1_000_000 * rate.output_usd_per_mtok
    )
    return cost, True
