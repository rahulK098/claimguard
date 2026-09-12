"""The human-approval gate, end to end: mint with claimguard, verify with
claims_system -- two independently-implemented sides of the same protocol
(see claims_system.auth and docs/adr/0007-hmac-approval-gate.md).
"""

from fastapi.testclient import TestClient

from claimguard.schemas.approval import ApprovalDecision, mint_approval_id
from claims_system.app import create_app
from claims_system.config import Settings as ClaimsSystemSettings

RUN_ID = "run-abc123"
CLAIM_ID = "CLM-001"


def _decision_body(decision: str = "approve", payout: float | None = 2100.0) -> dict[str, object]:
    return {"run_id": RUN_ID, "decision": decision, "payout_usd": payout, "actor": "adjuster-1"}


def test_decision_rejected_without_header(claims_system_settings: ClaimsSystemSettings) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post(f"/claims/{CLAIM_ID}/decision", json=_decision_body())
        assert resp.status_code == 403


def test_decision_rejected_with_forged_header(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(),
            headers={"X-Approval-Id": "0" * 64},
        )
        assert resp.status_code == 403


def test_decision_rejected_when_token_minted_for_a_different_claim(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    # Valid token, but for CLM-002 -- must not authorize a write to CLM-001.
    approval_id = mint_approval_id(
        claims_system_settings.approval_secret, RUN_ID, "CLM-002", ApprovalDecision.APPROVE
    )
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(),
            headers={"X-Approval-Id": approval_id},
        )
        assert resp.status_code == 403


def test_decision_rejected_when_token_minted_for_a_different_decision(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    # Valid token for a REJECT on this exact claim, but the body says APPROVE.
    approval_id = mint_approval_id(
        claims_system_settings.approval_secret, RUN_ID, CLAIM_ID, ApprovalDecision.REJECT
    )
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(decision="approve"),
            headers={"X-Approval-Id": approval_id},
        )
        assert resp.status_code == 403


def test_decision_rejected_for_unknown_claim_even_without_a_token(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post("/claims/CLM-DOES-NOT-EXIST/decision", json=_decision_body())
        assert resp.status_code == 404


def test_decision_accepted_with_a_valid_token_and_then_visible_via_get(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    approval_id = mint_approval_id(
        claims_system_settings.approval_secret, RUN_ID, CLAIM_ID, ApprovalDecision.APPROVE
    )
    with TestClient(create_app(claims_system_settings)) as client:
        post_resp = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(),
            headers={"X-Approval-Id": approval_id},
        )
        assert post_resp.status_code == 201
        assert post_resp.json()["decision"] == "approve"
        assert post_resp.json()["payout_usd"] == 2100.0

        get_resp = client.get(f"/claims/{CLAIM_ID}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["decision"] is not None
        assert body["decision"]["run_id"] == RUN_ID


def test_a_valid_token_still_cannot_write_a_second_decision(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    """'Valid id accepted once': individual token validity doesn't entitle a
    second write for a claim that already has a recorded decision."""
    approval_id = mint_approval_id(
        claims_system_settings.approval_secret, RUN_ID, CLAIM_ID, ApprovalDecision.APPROVE
    )
    with TestClient(create_app(claims_system_settings)) as client:
        first = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(),
            headers={"X-Approval-Id": approval_id},
        )
        assert first.status_code == 201

        # Mint a fresh, independently-valid token for the same triple and try again.
        second_approval_id = mint_approval_id(
            claims_system_settings.approval_secret, RUN_ID, CLAIM_ID, ApprovalDecision.APPROVE
        )
        second = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(),
            headers={"X-Approval-Id": second_approval_id},
        )
        assert second.status_code == 409


def test_reject_decision_carries_no_payout(claims_system_settings: ClaimsSystemSettings) -> None:
    approval_id = mint_approval_id(
        claims_system_settings.approval_secret, RUN_ID, CLAIM_ID, ApprovalDecision.REJECT
    )
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.post(
            f"/claims/{CLAIM_ID}/decision",
            json=_decision_body(decision="reject", payout=None),
            headers={"X-Approval-Id": approval_id},
        )
        assert resp.status_code == 201
        assert resp.json()["decision"] == "reject"
        assert resp.json()["payout_usd"] is None
