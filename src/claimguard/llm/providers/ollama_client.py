"""Local Ollama provider adapter.

No API key -- always eligible, and deliberately placed last in the default
fallback chain (`llm.fallback`): a developer's local model is a reasonable
safety net when every cloud provider fails, not a primary strategy. Tries
Ollama's structured-output mode (`format: <json_schema>`, supported on
modern Ollama versions) first, falling back to basic `format: "json"` mode
with a prompt-embedded schema for older versions.
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

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:3b",
        timeout: float = 120.0,  # local CPU inference can be slow
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
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
        url = f"{self._base_url}/api/generate"
        prompt = f"{system}\n\n{user}"

        resp = await self._post(
            url,
            {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": output_model.model_json_schema(),
            },
        )
        if resp.status_code >= 400:
            resp = await self._post(
                url,
                {
                    "model": self._model,
                    "prompt": f"{prompt}\n\n{build_schema_instructions(output_model)}",
                    "stream": False,
                    "format": "json",
                },
            )
        if resp.status_code >= 400:
            raise ProviderCallError(
                self.provider_name, f"HTTP {resp.status_code}: {resp.text[:300]}"
            )

        payload = resp.json()
        text = str(payload.get("response") or "")
        input_tokens = int(payload.get("prompt_eval_count") or 0)
        output_tokens = int(payload.get("eval_count") or 0)

        try:
            parsed = parse_structured_response(text, output_model)
        except JsonExtractionError as exc:
            raise ProviderCallError(self.provider_name, str(exc)) from exc

        latency_ms = (time.monotonic() - started) * 1000

        return LLMResult(
            parsed=parsed,
            provider=self.provider_name,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            # Local inference -- $0 is the correct, known cost, not a
            # placeholder (see docs/adr/0011).
            cost_usd=0.0,
            cost_priced=True,
            stop_reason=str(payload.get("done_reason") or "stop"),
            latency_ms=latency_ms,
            raw_text=parsed.model_dump_json(),
        )

    async def _post(self, url: str, body: dict[str, object]) -> httpx.Response:
        try:
            return await self._client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise ProviderCallError(self.provider_name, f"request failed: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
