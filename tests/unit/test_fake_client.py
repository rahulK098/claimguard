"""llm.fake.FakeClient -- the scripted client the graph test suite (Phase 4)
will drive every guard/routing path with."""

import pytest

from claimguard.llm.client import ProviderCallError
from claimguard.llm.fake import FakeClient
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


async def test_scripted_success_returns_the_scripted_value() -> None:
    output = _extractor_output()
    client = FakeClient({"extractor": output})
    result = await client.parse(
        node="extractor", system="sys", user="usr", output_model=ExtractorOutput
    )
    assert result.parsed == output
    assert result.provider == "fake"
    assert result.cost_usd == 0.0


async def test_scripted_exception_is_raised() -> None:
    client = FakeClient({"extractor": ProviderCallError("fake", "boom")})
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)


async def test_unscripted_node_raises() -> None:
    client = FakeClient({})
    with pytest.raises(ProviderCallError):
        await client.parse(node="reviewer", system="s", user="u", output_model=ExtractorOutput)


async def test_wrong_output_model_type_raises() -> None:
    client = FakeClient({"extractor": "not a pydantic model"})  # type: ignore[dict-item]
    with pytest.raises(ProviderCallError):
        await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)


async def test_records_call_history() -> None:
    client = FakeClient({"extractor": _extractor_output()})
    await client.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    assert client.calls == ["extractor"]
