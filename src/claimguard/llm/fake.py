"""Scripted LLM client for tests. No network, no key, no cost.

Script one response (or one exception) per node name. Used throughout the
graph test suite (Phase 4) to drive every guard/routing path deterministically.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from claimguard.llm.client import LLMResult, ProviderCallError

T = TypeVar("T", bound=BaseModel)


class FakeClient:
    provider_name = "fake"

    def __init__(self, script: dict[str, BaseModel | Exception]) -> None:
        self._script = script
        self.calls: list[str] = []

    async def parse(
        self,
        *,
        node: str,
        system: str,
        user: str,
        output_model: type[T],
        effort: str | None = None,
    ) -> LLMResult[T]:
        self.calls.append(node)
        if node not in self._script:
            raise ProviderCallError(self.provider_name, f"no scripted response for node {node!r}")

        outcome = self._script[node]
        if isinstance(outcome, Exception):
            raise outcome

        if not isinstance(outcome, output_model):
            raise ProviderCallError(
                self.provider_name,
                f"scripted response for node {node!r} is a {type(outcome).__name__}, "
                f"not the requested {output_model.__name__}",
            )

        return LLMResult(
            parsed=outcome,
            provider=self.provider_name,
            model="fake-model",
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.0,
            cost_priced=True,
            stop_reason="end_turn",
            latency_ms=0.0,
            raw_text=outcome.model_dump_json(),
        )

    async def aclose(self) -> None:
        return None
