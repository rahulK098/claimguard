from fastapi.testclient import TestClient

from casefile.api.app import create_app
from casefile.config import Settings
from claims_system.app import app as claims_system_app


def test_orchestrator_healthz(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "casefile-api"


def test_claims_system_healthz() -> None:
    client = TestClient(claims_system_app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["service"] == "claims-system"
