"""Generic OpenAI-chat-completions-shaped provider adapter.

Azure OpenAI, OpenRouter, Groq, and DeepSeek all speak (close enough to) the
same `/chat/completions` wire format -- one class, parameterized per
provider, instead of four near-identical copies. Azure's extra key-rotation
behavior is layered on top by `AzureOpenAIClient` below, which composes two
instances of this class rather than duplicating the request logic.

Two attempts per call: native `response_format: json_schema` first (most of
these providers, or the underlying model they route to, support it), then a
plain prompt-embedded-schema request with no `response_format` field at all
if the first attempt errors -- maximally compatible, since an unrecognized
field is far more likely to cause a hard failure than a missing one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider_name: str
    url: str
    headers: dict[str, str]
    model: str
    include_model_in_body: bool = True
    try_json_schema: bool = True
    rate: ModelRate | None = None


class OpenAICompatibleClient:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    @property
    def provider_name(self) -> str:
        return self._config.provider_name

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
        resp = await self._post(self._config.try_json_schema, system, user, output_model)
        if resp.status_code >= 400 and self._config.try_json_schema:
            resp = await self._post(False, system, user, output_model)
        if resp.status_code >= 400:
            raise ProviderCallError(
                self.provider_name, f"HTTP {resp.status_code}: {resp.text[:300]}"
            )

        payload = resp.json()
        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"] or ""
            finish_reason = str(choice.get("finish_reason") or "stop")
            usage = payload.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
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
            self._config.rate, input_tokens, output_tokens
        )

        return LLMResult(
            parsed=parsed,
            provider=self.provider_name,
            model=self._config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cost_priced=cost_priced,
            stop_reason=finish_reason,
            latency_ms=latency_ms,
            raw_text=parsed.model_dump_json(),
        )

    async def _post(
        self, with_json_schema: bool, system: str, user: str, output_model: type[T]
    ) -> httpx.Response:
        if with_json_schema:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            response_format: dict[str, object] | None = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "schema": output_model.model_json_schema(),
                    "strict": True,
                },
            }
        else:
            augmented_system = f"{system}\n\n{build_schema_instructions(output_model)}"
            messages = [
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": user},
            ]
            response_format = None

        body: dict[str, object] = {"messages": messages, "temperature": 0}
        if self._config.include_model_in_body:
            body["model"] = self._config.model
        if response_format is not None:
            body["response_format"] = response_format

        try:
            return await self._client.post(
                self._config.url, headers=self._config.headers, json=body
            )
        except httpx.HTTPError as exc:
            raise ProviderCallError(self.provider_name, f"request failed: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.aclose()


class AzureOpenAIClient:
    """Azure OpenAI with key rotation: tries each configured key in order,
    falling through to the next on failure, before the caller's fallback
    chain moves on to a different provider entirely."""

    provider_name = "azure"

    def __init__(
        self,
        *,
        endpoint: str,
        deployment: str,
        api_version: str,
        keys: list[str],
        rate: ModelRate | None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not keys:
            raise ValueError("AzureOpenAIClient requires at least one API key")
        url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={api_version}"
        )
        self._delegates = [
            OpenAICompatibleClient(
                OpenAICompatibleConfig(
                    provider_name=self.provider_name,
                    url=url,
                    headers={"api-key": key, "Content-Type": "application/json"},
                    model=deployment,
                    include_model_in_body=False,
                    rate=rate,
                ),
                timeout=timeout,
                transport=transport,
            )
            for key in keys
        ]

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        last_error: ProviderCallError | None = None
        for delegate in self._delegates:
            try:
                return await delegate.parse(
                    node=node, system=system, user=user, output_model=output_model, effort=effort
                )
            except ProviderCallError as exc:
                last_error = exc
                continue
        assert last_error is not None  # __init__ guarantees at least one delegate
        raise last_error

    async def aclose(self) -> None:
        for delegate in self._delegates:
            await delegate.aclose()
