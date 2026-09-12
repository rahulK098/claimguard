"""One real network call through whatever provider is actually configured.

Skipped entirely when no provider has credentials in the environment/.env --
this is the only test in the suite that spends real money or hits a real
network, and it respects "multi means whatever is present in .env should
work": it builds the exact same fallback chain the graph will use, from the
exact same settings.
"""

import pytest

from claimguard.llm.fallback import build_default_chain
from claimguard.llm.provider_settings import ProviderSettings, get_provider_settings
from claimguard.schemas.handoffs import ExtractorOutput

pytestmark = pytest.mark.live


def _any_provider_configured(settings: ProviderSettings) -> bool:
    return bool(
        settings.anthropic_api_key
        or (settings.azure_openai_key and settings.azure_openai_endpoint)
        or settings.openrouter_api_key
        or settings.groq_api_key
        or settings.gemini_api_key
        or settings.deepseek_api_key
    )


_SETTINGS = get_provider_settings()


@pytest.mark.skipif(
    not _any_provider_configured(_SETTINGS),
    reason="no LLM provider credentials configured in the environment/.env",
)
async def test_live_extractor_call_against_whatever_is_configured() -> None:
    chain = build_default_chain(_SETTINGS)
    try:
        result = await chain.parse(
            node="extractor",
            system=(
                "Extract the claim fields from the document below into the requested schema. "
                "damage_category must be one of: minor, moderate, major, total_loss."
            ),
            user=(
                "Claim CLM-LIVE-TEST, policy POL-1001, claimant CLT-2001. Rear-ended at a "
                "stoplight on 2026-02-03. Bumper cracked and taillight housing broken. "
                "Repair estimate: $2,100."
            ),
            output_model=ExtractorOutput,
        )
    finally:
        await chain.aclose()

    assert result.parsed.claim_id
    assert result.parsed.damage_estimate_usd > 0
    assert result.cost_usd >= 0.0
    print(f"\n[live smoke] provider={result.provider} model={result.model} "
          f"cost=${result.cost_usd:.6f} priced={result.cost_priced}")
