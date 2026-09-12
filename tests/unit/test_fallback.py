"""FallbackLLMClient: tries providers in order, catches ProviderCallError,
moves on; raises AllProvidersExhaustedError only once every provider failed."""

import pytest

from claimguard.llm.client import ProviderCallError
from claimguard.llm.fake import FakeClient
from claimguard.llm.fallback import AllProvidersExhaustedError, FallbackLLMClient
from claimguard.schemas.handoffs import DamageCategory, ExtractionConfidence, ExtractorOutput


def _extractor_output() -> ExtractorOutput:
    return ExtractorOutput(
        claim_id="CLM-1",
        policy_number="POL-1",
        claimant_id="CLT-1",
        incident_description="fender bender",
        damage_category=DamageCategory.MINOR,
        damage_estimate_usd=1200,
        extraction_confidence=ExtractionConfidence.HIGH,
    )


def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        FallbackLLMClient([])


async def test_uses_the_first_provider_when_it_succeeds() -> None:
    first = FakeClient({"extractor": _extractor_output()})
    second = FakeClient({"extractor": ProviderCallError("second", "should not be called")})
    chain = FallbackLLMClient([("first", first), ("second", second)])

    result = await chain.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.provider == "fake"
    assert second.calls == []  # never reached


async def test_falls_through_to_the_second_provider_on_failure() -> None:
    first = FakeClient({"extractor": ProviderCallError("first", "network error")})
    second = FakeClient({"extractor": _extractor_output()})
    chain = FallbackLLMClient([("first", first), ("second", second)])

    result = await chain.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    assert result.parsed.claim_id == "CLM-1"
    assert first.calls == ["extractor"]
    assert second.calls == ["extractor"]


async def test_raises_all_providers_exhausted_when_every_provider_fails() -> None:
    first = FakeClient({"extractor": ProviderCallError("first", "boom-1")})
    second = FakeClient({"extractor": ProviderCallError("second", "boom-2")})
    chain = FallbackLLMClient([("first", first), ("second", second)])

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await chain.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)

    attempts = exc_info.value.attempts
    assert [a.provider for a in attempts] == ["first", "second"]
    assert "boom-1" in attempts[0].error
    assert "boom-2" in attempts[1].error


async def test_provider_names_property() -> None:
    chain = FallbackLLMClient(
        [("a", FakeClient({})), ("b", FakeClient({})), ("c", FakeClient({}))]
    )
    assert chain.provider_names == ["a", "b", "c"]
