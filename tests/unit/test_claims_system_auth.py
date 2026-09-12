"""claims_system.auth.verify_approval_id, cross-checked against
claimguard.schemas.approval.mint_approval_id -- two independent
implementations of the same HMAC protocol (see ADR-0007)."""

from claimguard.schemas.approval import ApprovalDecision as GuardDecision
from claimguard.schemas.approval import mint_approval_id
from claims_system.auth import ApprovalDecision as ClaimsSystemDecision
from claims_system.auth import verify_approval_id


def test_a_token_minted_by_claimguard_verifies_in_claims_system() -> None:
    approval_id = mint_approval_id("secret", "run-1", "CLM-1", GuardDecision.APPROVE)
    assert verify_approval_id(
        "secret", "run-1", "CLM-1", ClaimsSystemDecision.APPROVE, approval_id
    )


def test_rejects_wrong_secret() -> None:
    approval_id = mint_approval_id("secret-a", "run-1", "CLM-1", GuardDecision.APPROVE)
    assert not verify_approval_id(
        "secret-b", "run-1", "CLM-1", ClaimsSystemDecision.APPROVE, approval_id
    )


def test_rejects_wrong_run_id() -> None:
    approval_id = mint_approval_id("secret", "run-1", "CLM-1", GuardDecision.APPROVE)
    assert not verify_approval_id(
        "secret", "run-2", "CLM-1", ClaimsSystemDecision.APPROVE, approval_id
    )


def test_rejects_wrong_claim_id() -> None:
    approval_id = mint_approval_id("secret", "run-1", "CLM-1", GuardDecision.APPROVE)
    assert not verify_approval_id(
        "secret", "run-1", "CLM-2", ClaimsSystemDecision.APPROVE, approval_id
    )


def test_rejects_wrong_decision() -> None:
    approval_id = mint_approval_id("secret", "run-1", "CLM-1", GuardDecision.APPROVE)
    assert not verify_approval_id(
        "secret", "run-1", "CLM-1", ClaimsSystemDecision.REJECT, approval_id
    )


def test_rejects_garbage_token() -> None:
    assert not verify_approval_id(
        "secret", "run-1", "CLM-1", ClaimsSystemDecision.APPROVE, "not-hex-at-all"
    )


def test_rejects_empty_token() -> None:
    assert not verify_approval_id("secret", "run-1", "CLM-1", ClaimsSystemDecision.APPROVE, "")
