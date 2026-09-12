"""Google Gemini provider adapter.

Tries Gemini's native `responseSchema` + `responseMimeType: application/json`
structured-output mode first (a real JSON-Schema-constrained decode, like
Anthropic's), falling back to a plain prompt-embedded schema if Gemini
rejects the schema shape (its OpenAPI-3.0-subset schema support doesn't
cover everything Pydantic's `model_json_schema()` can emit).
"""

from __future__ import annotations

import time
from typing import TypeVar

import httpx
from pydantic import BaseModel

from claimguard.llm.client import LLMResult, ProviderCallError
from claimguard.llm.json_extraction import (
    JsonExtractionError,
    build_schema_instructions,
    parse_structured_response,
)
from claimguard.llm.pricing import ModelRate, compute_cost_usd_or_zero

T = TypeVar("T", bound=BaseModel)

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient:
    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
        rate: ModelRate | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._rate = rate
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

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
        url = f"{_API_BASE}/{self._model}:generateContent"
        combined_prompt = f"{system}\n\n{user}"

        resp = await self._post(
            url,
            {
                "contents": [{"parts": [{"text": combined_prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                    "responseSchema": output_model.model_json_schema(),
                },
            },
        )
        if resp.status_code >= 400:
            resp = await self._post(
                url,
                {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"{combined_prompt}\n\n"
                                    f"{build_schema_instructions(output_model)}"
                                }
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                },
            )
        if resp.status_code >= 400:
            raise ProviderCallError(
                self.provider_name, f"HTTP {resp.status_code}: {resp.text[:300]}"
            )

        payload = resp.json()
        try:
            candidate = payload["candidates"][0]
            text = candidate["content"]["parts"][0]["text"]
            finish_reason = str(candidate.get("finishReason") or "STOP")
            usage = payload.get("usageMetadata") or {}
            input_tokens = int(usage.get("promptTokenCount", 0))
            output_tokens = int(usage.get("candidatesTokenCount", 0))
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderCallError(
                self.provider_name, f"unexpected response shape: {exc}"
            ) from exc

        try:
            parsed = parse_structured_response(text, output_model)
        except JsonExtractionError as exc:
            raise ProviderCallError(self.provider_name, str(exc)) from exc

        latency_ms = (time.monotonic() - started) * 1000
        cost_usd, cost_priced = compute_cost_usd_or_zero(
            self._rate, input_tokens, output_tokens
        )

        return LLMResult(
            parsed=parsed,
            provider=self.provider_name,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cost_priced=cost_priced,
            stop_reason=finish_reason,
            latency_ms=latency_ms,
            raw_text=parsed.model_dump_json(),
        )

    async def _post(self, url: str, body: dict[str, object]) -> httpx.Response:
        try:
            headers = {"x-goog-api-key": self._api_key}
            return await self._client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ProviderCallError(self.provider_name, f"request failed: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
