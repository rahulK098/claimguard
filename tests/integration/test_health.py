from fastapi.testclient import TestClient

from claimguard.api.app import create_app
from claimguard.config import Settings
from claims_system.app import app as claims_system_app


def test_orchestrator_healthz(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "claimguard-api"


def test_claims_system_healthz() -> None:
    client = TestClient(claims_system_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "claims-system"
