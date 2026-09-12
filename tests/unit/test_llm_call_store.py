"""store.steps.LlmCallStore against a real (throwaway) SQLite file."""

from pathlib import Path

import pytest

from claimguard.store.db import connect
from claimguard.store.steps import LlmCallStore


@pytest.fixture
def store(tmp_path: Path) -> LlmCallStore:
    conn = connect(tmp_path / "test.db")
    return LlmCallStore(conn)


def test_next_call_index_starts_at_zero(store: LlmCallStore) -> None:
    assert store.next_call_index("run-1") == 0


def test_next_call_index_increments_after_a_record(store: LlmCallStore) -> None:
    store.record_llm_call(
        run_id="run-1", call_index=0, node="extractor", provider="fake", model="fake-model",
        request={"a": 1}, response="{}", input_tokens=1, output_tokens=1, cost_usd=0.0,
        cost_priced=True, stop_reason="end_turn", latency_ms=1.0, error=None,
    )
    assert store.next_call_index("run-1") == 1


def test_next_call_index_is_independent_per_run(store: LlmCallStore) -> None:
    store.record_llm_call(
        run_id="run-1", call_index=0, node="extractor", provider="fake", model="fake-model",
        request={}, response="{}", input_tokens=0, output_tokens=0, cost_usd=0.0,
        cost_priced=True, stop_reason="end_turn", latency_ms=0.0, error=None,
    )
    assert store.next_call_index("run-2") == 0


def test_get_llm_calls_round_trips_in_order(store: LlmCallStore) -> None:
    for i in range(3):
        store.record_llm_call(
            run_id="run-1", call_index=i, node=f"node-{i}", provider="fake", model="fake-model",
            request={"i": i}, response=f'{{"i": {i}}}', input_tokens=i, output_tokens=i,
            cost_usd=float(i), cost_priced=True, stop_reason="end_turn", latency_ms=float(i),
            error=None,
        )
    records = store.get_llm_calls("run-1")
    assert [r.call_index for r in records] == [0, 1, 2]
    assert [r.node for r in records] == ["node-0", "node-1", "node-2"]


def test_get_llm_calls_empty_for_unknown_run(store: LlmCallStore) -> None:
    assert store.get_llm_calls("no-such-run") == []


def test_error_record_round_trips(store: LlmCallStore) -> None:
    store.record_llm_call(
        run_id="run-1", call_index=0, node="extractor", provider="azure", model="",
        request={}, response=None, input_tokens=0, output_tokens=0, cost_usd=0.0,
        cost_priced=True, stop_reason="error", latency_ms=None, error="HTTP 500: boom",
    )
    record = store.get_llm_calls("run-1")[0]
    assert record.error == "HTTP 500: boom"
    assert record.response is None


def test_cost_priced_flag_round_trips(store: LlmCallStore) -> None:
    store.record_llm_call(
        run_id="run-1", call_index=0, node="extractor", provider="azure", model="chat",
        request={}, response="{}", input_tokens=10, output_tokens=10, cost_usd=0.0,
        cost_priced=False, stop_reason="stop", latency_ms=5.0, error=None,
    )
    record = store.get_llm_calls("run-1")[0]
    assert record.cost_priced is False
