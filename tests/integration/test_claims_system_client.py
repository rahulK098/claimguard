"""claimguard.tools.claims_system.ClaimsSystemClient against a live in-process app."""

import pytest

from claimguard.schemas.approval import ApprovalDecision, mint_approval_id
from claimguard.schemas.claim import DamageCategory
from claimguard.tools.claims_system import (
    ClaimsSystemClient,
    DecisionRejectedError,
    NotFoundError,
)


async def test_get_policy(claims_system_client: ClaimsSystemClient) -> None:
    policy = await claims_system_client.get_policy("POL-1001")
    assert policy.holder_name == "Maria Alvarez"


async def test_get_policy_not_found_raises(claims_system_client: ClaimsSystemClient) -> None:
    with pytest.raises(NotFoundError):
        await claims_system_client.get_policy("POL-9999")


async def test_get_prior_claims(claims_system_client: ClaimsSystemClient) -> None:
    priors = await claims_system_client.get_prior_claims("CLT-2013")
    assert len(priors) == 3


async def test_get_prior_claims_not_found_raises(claims_system_client: ClaimsSystemClient) -> None:
    with pytest.raises(NotFoundError):
        await claims_system_client.get_prior_claims("CLT-9999")


async def test_get_repair_cost_benchmarks(claims_system_client: ClaimsSystemClient) -> None:
    benchmarks = await claims_system_client.get_repair_cost_benchmarks()
    assert set(benchmarks) == set(DamageCategory)
    assert benchmarks[DamageCategory.MINOR].low_usd < benchmarks[DamageCategory.MINOR].high_usd


async def test_get_decision_status_unknown_claim_raises(
    claims_system_client: ClaimsSystemClient,
) -> None:
    with pytest.raises(NotFoundError):
        await claims_system_client.get_decision_status("CLM-DOES-NOT-EXIST")


async def test_submit_decision_without_valid_approval_raises(
    claims_system_client: ClaimsSystemClient,
) -> None:
    with pytest.raises(DecisionRejectedError):
        await claims_system_client.submit_decision(
            "CLM-002",
            run_id="run-1",
            decision=ApprovalDecision.APPROVE,
            approval_id="not-a-real-token",
            payout_usd=1450.0,
        )


async def test_submit_decision_success_then_visible_in_status(
    claims_system_client: ClaimsSystemClient,
) -> None:
    approval_id = mint_approval_id("test-secret", "run-1", "CLM-002", ApprovalDecision.APPROVE)
    record = await claims_system_client.submit_decision(
        "CLM-002",
        run_id="run-1",
        decision=ApprovalDecision.APPROVE,
        approval_id=approval_id,
        payout_usd=1450.0,
        actor="adjuster-2",
    )
    assert record["decision"] == "approve"
    assert record["payout_usd"] == 1450.0

    status = await claims_system_client.get_decision_status("CLM-002")
    assert status["decision"]["actor"] == "adjuster-2"
