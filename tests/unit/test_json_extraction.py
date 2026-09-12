"""llm.json_extraction: the shared "pull JSON out of free text, validate
against a Pydantic model" path every non-native-structured-output provider
adapter uses."""

import pytest

from claimguard.llm.json_extraction import (
    JsonExtractionError,
    build_schema_instructions,
    extract_json_object,
    parse_structured_response,
)
from claimguard.schemas.handoffs import DamageCategory, ExtractionConfidence, ExtractorOutput

VALID_PAYLOAD = (
    '{"claim_id": "CLM-1", "policy_number": "POL-1", "claimant_id": "CLT-1", '
    '"incident_description": "fender bender", "damage_category": "minor", '
    '"damage_estimate_usd": 1200, "extraction_confidence": "high", "missing_fields": []}'
)


def test_extract_bare_object() -> None:
    assert extract_json_object(f"  {VALID_PAYLOAD}  ") == VALID_PAYLOAD


def test_extract_fenced_object() -> None:
    raw = f"Here is the result:\n```json\n{VALID_PAYLOAD}\n```\nLet me know if you need more."
    assert extract_json_object(raw) == VALID_PAYLOAD


def test_extract_fenced_object_without_language_tag() -> None:
    raw = f"```\n{VALID_PAYLOAD}\n```"
    assert extract_json_object(raw) == VALID_PAYLOAD


def test_extract_raises_when_no_json_present() -> None:
    with pytest.raises(JsonExtractionError):
        extract_json_object("Sorry, I can't help with that.")


def test_parse_structured_response_success() -> None:
    result = parse_structured_response(VALID_PAYLOAD, ExtractorOutput)
    assert isinstance(result, ExtractorOutput)
    assert result.claim_id == "CLM-1"
    assert result.damage_category == DamageCategory.MINOR
    assert result.extraction_confidence == ExtractionConfidence.HIGH


def test_parse_structured_response_wraps_validation_error() -> None:
    with pytest.raises(JsonExtractionError):
        parse_structured_response('{"claim_id": "CLM-1"}', ExtractorOutput)


def test_parse_structured_response_wraps_missing_json() -> None:
    with pytest.raises(JsonExtractionError):
        parse_structured_response("no json here at all", ExtractorOutput)


def test_build_schema_instructions_embeds_the_schema() -> None:
    instructions = build_schema_instructions(ExtractorOutput)
    assert "JSON Schema" in instructions
    assert "damage_category" in instructions
    assert "No prose" in instructions
