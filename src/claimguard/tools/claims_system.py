"""Async httpx client the graph's Investigator and writeback nodes (Phase 4)
use to talk to the mock claims system.

No retry or circuit-breaker logic lives here on purpose — the Supervisor's
guards (step/LLM-call/budget ceilings, Phase 4) are what bound a run; a
client-level retry loop would be a second, uncoordinated place a run could
spend time and money outside those guards.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

import httpx

from claimguard.fixtures import RepairCostBucket
from claimguard.schemas.approval import ApprovalDecision
from claimguard.schemas.claim import DamageCategory, PolicyRecord, PriorClaim


class ClaimsSystemError(Exception):
    """Base class for errors talking to the claims system."""


class NotFoundError(ClaimsSystemError):
    """The claims system has no record of the requested policy/claimant/claim."""


class DecisionRejectedError(ClaimsSystemError):
    """The claims system refused a decision write (bad/missing approval, or already decided)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"decision write rejected ({status_code}): {detail}")
        self.status_code = status_code
        self.detail = detail


class DecisionRecord(dict[str, object]):
    """The claims system's response to a successful decision write, as raw JSON.

    Kept untyped-Pydantic on purpose here: the caller (Phase 4's writeback
    node) only needs to confirm the write succeeded and log the response;
    it does not need to further branch on its shape.
    """


class ClaimsSystemClient:
    """Async client for the mock claims system's read and decision endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def get_policy(self, policy_number: str) -> PolicyRecord:
        resp = await self._client.get(f"/policies/{policy_number}")
        if resp.status_code == 404:
            raise NotFoundError(f"unknown policy_number {policy_number!r}")
        resp.raise_for_status()
        return PolicyRecord.model_validate(resp.json())

    async def get_prior_claims(self, claimant_id: str) -> list[PriorClaim]:
        resp = await self._client.get(f"/claimants/{claimant_id}/prior-claims")
        if resp.status_code == 404:
            raise NotFoundError(f"unknown claimant_id {claimant_id!r}")
        resp.raise_for_status()
        return [PriorClaim.model_validate(item) for item in resp.json()]

    async def get_repair_cost_benchmarks(self) -> dict[DamageCategory, RepairCostBucket]:
        resp = await self._client.get("/benchmarks/repair-cost")
        resp.raise_for_status()
        return {
            DamageCategory(key): RepairCostBucket.model_validate(value)
            for key, value in resp.json().items()
        }

    async def get_decision_status(self, claim_id: str) -> dict[str, object]:
        resp = await self._client.get(f"/claims/{claim_id}")
        if resp.status_code == 404:
            raise NotFoundError(f"unknown claim_id {claim_id!r}")
        resp.raise_for_status()
        json_body: dict[str, object] = resp.json()
        return json_body

    async def submit_decision(
        self,
        claim_id: str,
        *,
        run_id: str,
        decision: ApprovalDecision,
        approval_id: str,
        payout_usd: float | None = None,
        actor: str = "unspecified-human",
    ) -> DecisionRecord:
        resp = await self._client.post(
            f"/claims/{claim_id}/decision",
            json={
                "run_id": run_id,
                "decision": decision.value,
                "payout_usd": payout_usd,
                "actor": actor,
            },
            headers={"X-Approval-Id": approval_id},
        )
        if resp.status_code in (403, 404, 409):
            raise DecisionRejectedError(resp.status_code, resp.text)
        resp.raise_for_status()
        return DecisionRecord(resp.json())

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
