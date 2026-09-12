"""claims_system.data.ClaimsSystemData in isolation, loaded from the real fixtures."""

from pathlib import Path

import pytest

from claimguard.schemas.claim import DamageCategory
from claims_system.data import ClaimsSystemData

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "data" / "claims"
BENCHMARKS_PATH = REPO_ROOT / "data" / "benchmarks" / "repair_costs.json"


@pytest.fixture
def data() -> ClaimsSystemData:
    return ClaimsSystemData(FIXTURES_DIR, BENCHMARKS_PATH)


def test_is_known_claim(data: ClaimsSystemData) -> None:
    assert data.is_known_claim("CLM-001")
    assert not data.is_known_claim("CLM-DOES-NOT-EXIST")


def test_get_policy_known(data: ClaimsSystemData) -> None:
    policy = data.get_policy("POL-1001")
    assert policy is not None
    assert policy.holder_name == "Maria Alvarez"


def test_get_policy_unknown_returns_none(data: ClaimsSystemData) -> None:
    assert data.get_policy("POL-9999") is None


def test_get_prior_claims_distinguishes_unknown_from_empty(data: ClaimsSystemData) -> None:
    assert data.get_prior_claims("CLT-2001") == []  # known claimant, no priors
    assert data.get_prior_claims("CLT-9999") is None  # unknown claimant


def test_get_prior_claims_nonempty(data: ClaimsSystemData) -> None:
    priors = data.get_prior_claims("CLT-2013")
    assert priors is not None
    assert len(priors) == 3


def test_benchmarks_cover_every_damage_category(data: ClaimsSystemData) -> None:
    assert set(data.benchmarks) == set(DamageCategory)
