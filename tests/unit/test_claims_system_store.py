"""claims_system.store.DecisionStore in isolation, no HTTP involved."""

from pathlib import Path

import pytest

from claims_system.auth import ApprovalDecision
from claims_system.store import DecisionAlreadyRecordedError, DecisionStore


@pytest.fixture
def store(tmp_path: Path) -> DecisionStore:
    return DecisionStore(tmp_path / "decisions.db")


def test_get_returns_none_for_unrecorded_claim(store: DecisionStore) -> None:
    assert store.get("CLM-1") is None


def test_record_then_get_round_trips(store: DecisionStore) -> None:
    record = store.record("CLM-1", "run-1", ApprovalDecision.APPROVE, 1500.0, "adjuster-1")
    assert record.claim_id == "CLM-1"
    assert record.payout_usd == 1500.0

    fetched = store.get("CLM-1")
    assert fetched == record


def test_second_record_for_same_claim_raises(store: DecisionStore) -> None:
    store.record("CLM-1", "run-1", ApprovalDecision.APPROVE, 1500.0, "adjuster-1")
    with pytest.raises(DecisionAlreadyRecordedError):
        store.record("CLM-1", "run-2", ApprovalDecision.REJECT, None, "adjuster-2")

    # The original record is untouched by the failed second attempt.
    assert store.get("CLM-1").run_id == "run-1"  # type: ignore[union-attr]


def test_reject_decision_has_no_payout(store: DecisionStore) -> None:
    record = store.record("CLM-2", "run-1", ApprovalDecision.REJECT, None, "adjuster-1")
    assert record.payout_usd is None


def test_persists_across_store_instances_on_same_file(tmp_path: Path) -> None:
    db_path = tmp_path / "decisions.db"
    DecisionStore(db_path).record("CLM-1", "run-1", ApprovalDecision.APPROVE, 100.0, "a")

    reopened = DecisionStore(db_path)
    fetched = reopened.get("CLM-1")
    assert fetched is not None
    assert fetched.payout_usd == 100.0
