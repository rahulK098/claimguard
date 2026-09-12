"""RecordingClient + ReplayClient: the mechanism behind "replay is not the
same as resume" (ADR-0006). Recording wraps a FakeClient here so the test
never touches the network; replay then re-serves exactly what was recorded,
proving determinism without depending on any real provider's behavior."""

from pathlib import Path

import pytest

from claimguard.llm.client import ProviderCallError
from claimguard.llm.fake import FakeClient
from claimguard.llm.recording import RecordingClient, ReplayClient, ReplayExhaustedError
from claimguard.schemas.handoffs import DamageCategory, ExtractionConfidence, ExtractorOutput
from claimguard.store.db import connect
from claimguard.store.steps import LlmCallStore


def _extractor_output(claim_id: str = "CLM-1") -> ExtractorOutput:
    return ExtractorOutput(
        claim_id=claim_id,
        policy_number="POL-1",
        claimant_id="CLT-1",
        incident_description="fender bender",
        damage_category=DamageCategory.MINOR,
        damage_estimate_usd=1200,
        extraction_confidence=ExtractionConfidence.HIGH,
    )


@pytest.fixture
def store(tmp_path: Path) -> LlmCallStore:
    return LlmCallStore(connect(tmp_path / "test.db"))


async def test_recording_client_persists_a_successful_call(store: LlmCallStore) -> None:
    output = _extractor_output()
    fake = FakeClient({"extractor": output})
    recorder = RecordingClient(fake, store, run_id="run-1")

    result = await recorder.parse(
        node="extractor", system="sys", user="usr", output_model=ExtractorOutput
    )

    assert result.parsed == output
    records = store.get_llm_calls("run-1")
    assert len(records) == 1
    assert records[0].node == "extractor"
    assert records[0].provider == "fake"
    assert records[0].error is None


async def test_recording_client_persists_a_failed_call(store: LlmCallStore) -> None:
    fake = FakeClient({"extractor": ProviderCallError("fake", "boom")})
    recorder = RecordingClient(fake, store, run_id="run-1")

    with pytest.raises(ProviderCallError):
        await recorder.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)

    records = store.get_llm_calls("run-1")
    assert len(records) == 1
    assert records[0].error == "boom"  # exc.detail, not str(exc) -- provider is its own column
    assert records[0].response is None


async def test_recording_client_call_indices_increment(store: LlmCallStore) -> None:
    fake = FakeClient(
        {"extractor": _extractor_output(), "investigator": _extractor_output("CLM-2")}
    )
    recorder = RecordingClient(fake, store, run_id="run-1")

    await recorder.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await recorder.parse(node="investigator", system="s", user="u", output_model=ExtractorOutput)

    records = store.get_llm_calls("run-1")
    assert [r.call_index for r in records] == [0, 1]


async def test_replay_client_serves_recorded_calls_in_order(store: LlmCallStore) -> None:
    fake = FakeClient(
        {"extractor": _extractor_output("CLM-1"), "investigator": _extractor_output("CLM-2")}
    )
    recorder = RecordingClient(fake, store, run_id="source-run")
    await recorder.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
    await recorder.parse(node="investigator", system="s", user="u", output_model=ExtractorOutput)

    replay = ReplayClient(store, source_run_id="source-run")
    first = await replay.parse(
        node="extractor", system="s", user="u", output_model=ExtractorOutput
    )
    second = await replay.parse(
        node="investigator", system="s", user="u", output_model=ExtractorOutput
    )

    assert first.parsed.claim_id == "CLM-1"
    assert second.parsed.claim_id == "CLM-2"
    assert first.provider == "fake"  # replay preserves the original provider, not "replay"


async def test_replay_client_raises_when_asked_for_more_than_was_recorded(
    store: LlmCallStore,
) -> None:
    fake = FakeClient({"extractor": _extractor_output()})
    recorder = RecordingClient(fake, store, run_id="source-run")
    await recorder.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)

    replay = ReplayClient(store, source_run_id="source-run")
    await replay.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)

    with pytest.raises(ReplayExhaustedError):
        await replay.parse(node="investigator", system="s", user="u", output_model=ExtractorOutput)


async def test_replay_client_reraises_a_recorded_failure(store: LlmCallStore) -> None:
    fake = FakeClient({"extractor": ProviderCallError("azure", "HTTP 500")})
    recorder = RecordingClient(fake, store, run_id="source-run")
    with pytest.raises(ProviderCallError):
        await recorder.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)

    replay = ReplayClient(store, source_run_id="source-run")
    with pytest.raises(ProviderCallError):
        await replay.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)


async def test_replay_client_of_empty_source_run_is_immediately_exhausted(
    store: LlmCallStore,
) -> None:
    replay = ReplayClient(store, source_run_id="never-ran")
    with pytest.raises(ReplayExhaustedError):
        await replay.parse(node="extractor", system="s", user="u", output_model=ExtractorOutput)
