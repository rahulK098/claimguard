"""Recording and replay of LLM calls -- the mechanism behind ADR-0006's
"replay is not the same thing as resume" guarantee.

`RecordingClient` wraps any `LLMClient` (typically the outermost
`FallbackLLMClient`) and persists every attempt -- success or failure -- to
`llm_calls`. `ReplayClient` serves those recorded responses back in order
for a *new* run against the *same* fixture, with no network call and no
cost: replaying a past decision means re-validating the exact JSON that was
returned last time, not asking a non-deterministic model the same question
again and hoping for the same answer.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from claimguard.llm.client import LLMClient, LLMResult, ProviderCallError
from claimguard.store.steps import LlmCallStore

T = TypeVar("T", bound=BaseModel)


class RecordingClient:
    """Wraps one LLMClient, persisting every call attempt to `llm_calls`."""

    def __init__(self, inner: LLMClient, store: LlmCallStore, run_id: str) -> None:
        self._inner = inner
        self._store = store
        self._run_id = run_id

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        call_index = self._store.next_call_index(self._run_id)
        request: dict[str, object] = {
            "system": system,
            "user": user,
            "output_model": output_model.__name__,
            "effort": effort,
        }
        try:
            result = await self._inner.parse(
                node=node, system=system, user=user, output_model=output_model, effort=effort
            )
        except ProviderCallError as exc:
            self._store.record_llm_call(
                run_id=self._run_id,
                call_index=call_index,
                node=node,
                provider=exc.provider,
                model="",
                request=request,
                response=None,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cost_priced=True,
                stop_reason="error",
                latency_ms=None,
                error=exc.detail,
            )
            raise

        self._store.record_llm_call(
            run_id=self._run_id,
            call_index=call_index,
            node=node,
            provider=result.provider,
            model=result.model,
            request=request,
            response=result.raw_text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            cost_priced=result.cost_priced,
            stop_reason=result.stop_reason,
            latency_ms=result.latency_ms,
            error=None,
        )
        return result

    async def aclose(self) -> None:
        aclose = getattr(self._inner, "aclose", None)
        if aclose is not None:
            await aclose()


class ReplayExhaustedError(Exception):
    """Raised when a replay asks for more calls than were recorded on the
    source run -- proof the replayed path diverged from the original."""


class ReplayClient:
    """Serves a prior run's recorded LLM calls back in order. No network."""

    provider_name = "replay"

    def __init__(self, store: LlmCallStore, source_run_id: str) -> None:
        self._source_run_id = source_run_id
        self._records = store.get_llm_calls(source_run_id)
        self._next_index = 0

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        if self._next_index >= len(self._records):
            raise ReplayExhaustedError(
                f"replay of run {self._source_run_id!r} has no recorded call at index "
                f"{self._next_index} (only {len(self._records)} were recorded) -- the "
                "replayed path diverged from the original run"
            )
        record = self._records[self._next_index]
        self._next_index += 1

        if record.error is not None:
            raise ProviderCallError(record.provider or "unknown", record.error)

        parsed = output_model.model_validate_json(record.response or "")
        return LLMResult(
            parsed=parsed,
            provider=record.provider,
            model=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            cost_usd=record.cost_usd,
            cost_priced=record.cost_priced,
            stop_reason=record.stop_reason or "end_turn",
            latency_ms=record.latency_ms or 0.0,
            raw_text=record.response or "",
        )

    async def aclose(self) -> None:
        return None
