"""Anthropic provider adapter.

Uses `client.messages.create(..., output_config={"format": {...}})` directly
rather than the `.parse()` convenience wrapper, and validates the returned
text through the same `parse_structured_response` helper every other
provider uses. That's a deliberate uniformity choice: every adapter in this
project converges on "get raw text back, then one shared JSON-extraction +
Pydantic-validation step" -- see docs/adr/0011-multi-provider-llm.md. It
also means Anthropic's own structured-outputs guarantee (the response is
schema-valid JSON before we ever see it) still runs through the exact same
domain validators (ADR-0003) as a provider with no native structured-output
support at all.
"""

from __future__ import annotations

import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from claimguard.llm.client import LLMResult, ProviderCallError
from claimguard.llm.json_extraction import JsonExtractionError, parse_structured_response
from claimguard.llm.pricing import compute_cost_usd

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    provider_name = "anthropic"

    def __init__(
        self, *, api_key: str, model: str = "claude-opus-5", max_tokens: int = 4096
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        started = time.monotonic()
        output_config: dict[str, object] = {
            "format": {"type": "json_schema", "schema": output_model.model_json_schema()}
        }
        if effort is not None:
            output_config["effort"] = effort

        try:
            response = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,
                thinking={"type": "adaptive"},
            )
        except anthropic.APIError as exc:
            raise ProviderCallError(self.provider_name, f"API error: {exc}") from exc

        latency_ms = (time.monotonic() - started) * 1000

        if response.stop_reason == "refusal":
            raise ProviderCallError(self.provider_name, "model refused the request")

        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raise ProviderCallError(
                self.provider_name,
                f"no text content in response (stop_reason={response.stop_reason})",
            )

        try:
            parsed = parse_structured_response(text_blocks[0], output_model)
        except JsonExtractionError as exc:
            raise ProviderCallError(self.provider_name, str(exc)) from exc

        cost_usd = compute_cost_usd(
            self._model, response.usage.input_tokens, response.usage.output_tokens
        )

        return LLMResult(
            parsed=parsed,
            provider=self.provider_name,
            model=self._model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=cost_usd,
            cost_priced=True,
            stop_reason=response.stop_reason or "end_turn",
            latency_ms=latency_ms,
            raw_text=parsed.model_dump_json(),
        )

    async def aclose(self) -> None:
        await self._client.close()
