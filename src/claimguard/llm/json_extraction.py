"""Shared "extract a JSON object from free-form model output, then validate
against a Pydantic model" path, used by every provider adapter that doesn't
have (or falls back from) native schema-constrained decoding.

This is deliberately the *same* code path for every provider: it's what
makes ADR-0003's domain-layer validators do real work across a
heterogeneous set of providers, not just Anthropic's structured outputs.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class JsonExtractionError(Exception):
    """Raised when a response contains no JSON object, or it doesn't
    validate against the requested output model."""


def extract_json_object(raw: str) -> str:
    """Pulls one JSON object out of free-form text.

    Tries a fenced ```json ... ``` block first (common when a model wraps
    its answer in prose despite instructions not to), then the largest
    brace-delimited span.
    """
    fenced = _FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1)
    match = _OBJECT_RE.search(raw)
    if not match:
        raise JsonExtractionError(f"no JSON object found in response: {raw[:200]!r}")
    return match.group()


def parse_structured_response(raw: str, output_model: type[T]) -> T:
    """extract_json_object + Pydantic validation, wrapped as one JsonExtractionError."""
    candidate = extract_json_object(raw)
    try:
        return output_model.model_validate_json(candidate)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise JsonExtractionError(
            f"response did not validate against {output_model.__name__}: {exc}"
        ) from exc


def build_schema_instructions(output_model: type[BaseModel]) -> str:
    """Prompt text asking a model to emit exactly one JSON object matching a schema.

    Used as the degraded path when a provider's native structured-output
    mode is unavailable or rejects the schema.
    """
    schema = json.dumps(output_model.model_json_schema(), indent=2)
    return (
        "Respond with ONLY a single JSON object matching this JSON Schema exactly. "
        "No prose, no markdown code fences, no explanation before or after the JSON.\n\n"
        f"JSON Schema:\n{schema}"
    )
