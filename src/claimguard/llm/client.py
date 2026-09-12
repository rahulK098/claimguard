"""The LLM client protocol every provider adapter, and every decorator
(Recording, Replay, Fallback, Fake) implements identically.

A graph node (Phase 4) only ever depends on this protocol — it never knows
or cares whether the answer came from Anthropic, Azure, a fallback chain,
or a replayed recording. That substitutability is what makes replay and
testing possible without touching node code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderCallError(Exception):
    """One provider attempt did not produce a usable structured response.

    Covers network failure, a non-2xx response, a refusal, an empty
    response, or a response that failed JSON extraction/schema validation.
    Callers (the fallback chain) catch this specifically and move on to the
    next provider; anything else (a programming error) is left to propagate.
    """

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(f"[{provider}] {detail}")
        self.provider = provider
        self.detail = detail


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    """One successful call's result, provider-agnostic.

    `raw_text` is always *exactly* the JSON text that validates as the
    requested output model — never a full provider-specific envelope. That
    uniformity is what lets `ReplayClient` re-validate a recorded response
    the same way regardless of which provider originally produced it.
    """

    parsed: T
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_priced: bool  # False => cost_usd is a 0.0 placeholder, not a real accounted cost
    stop_reason: str
    latency_ms: float
    raw_text: str


class LLMClient(Protocol):
    """Structural protocol — any object with a matching `parse` is an LLMClient.

    `effort` is accepted by every implementation (Anthropic supports it
    natively; others accept and ignore it) so callers don't need to branch
    on provider to pass a per-node effort hint.
    """

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]: ...
