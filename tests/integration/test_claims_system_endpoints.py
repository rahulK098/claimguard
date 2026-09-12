"""Read endpoints and the claim-status endpoint, exercised over real HTTP semantics."""

from fastapi.testclient import TestClient

from claims_system.app import create_app
from claims_system.config import Settings as ClaimsSystemSettings


def test_get_known_policy(claims_system_settings: ClaimsSystemSettings) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/policies/POL-1001")
        assert resp.status_code == 200
        assert resp.json()["holder_name"] == "Maria Alvarez"


def test_get_unknown_policy_404(claims_system_settings: ClaimsSystemSettings) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/policies/POL-9999")
        assert resp.status_code == 404


def test_get_prior_claims_known_claimant_no_priors(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/claimants/CLT-2001/prior-claims")
        assert resp.status_code == 200
        assert resp.json() == []


def test_get_prior_claims_known_claimant_with_priors(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/claimants/CLT-2013/prior-claims")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


def test_get_prior_claims_unknown_claimant_404(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/claimants/CLT-9999/prior-claims")
        assert resp.status_code == 404


def test_get_repair_cost_benchmarks_covers_all_categories(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/benchmarks/repair-cost")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"minor", "moderate", "major", "total_loss"}
        assert body["minor"]["low_usd"] < body["minor"]["high_usd"]


def test_get_claim_status_unknown_claim_404(claims_system_settings: ClaimsSystemSettings) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/claims/CLM-DOES-NOT-EXIST")
        assert resp.status_code == 404


def test_get_claim_status_known_claim_no_decision_yet(
    claims_system_settings: ClaimsSystemSettings,
) -> None:
    with TestClient(create_app(claims_system_settings)) as client:
        resp = client.get("/claims/CLM-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["claim_id"] == "CLM-001"
        assert body["decision"] is None
