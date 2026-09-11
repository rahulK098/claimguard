"""Validates the 30 synthetic claim fixtures as a set (the project's eval data)."""

from pathlib import Path

import pytest

from claimguard.fixtures import (
    load_all_fixtures,
    load_fixture_by_id,
    load_fixtures_by_category,
    load_repair_cost_benchmarks,
)
from claimguard.schemas.claim import ClaimCategory, DamageCategory

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "data" / "claims"
BENCHMARKS_PATH = REPO_ROOT / "data" / "benchmarks" / "repair_costs.json"


def test_exactly_thirty_fixtures_present() -> None:
    assert len(load_all_fixtures(FIXTURES_DIR)) == 30


def test_all_claim_ids_unique() -> None:
    fixtures = load_all_fixtures(FIXTURES_DIR)
    ids = [f.claim_id for f in fixtures]
    assert len(ids) == len(set(ids))


def test_category_composition_matches_the_brief() -> None:
    by_category = load_fixtures_by_category(FIXTURES_DIR)
    assert len(by_category[ClaimCategory.CLEAN]) == 10
    assert len(by_category[ClaimCategory.DISCREPANCY]) == 10
    assert len(by_category[ClaimCategory.STRESS]) == 5
    assert len(by_category[ClaimCategory.EDGE]) == 5


def test_clean_fixtures_expect_approve_with_no_send_backs() -> None:
    by_category = load_fixtures_by_category(FIXTURES_DIR)
    for fixture in by_category[ClaimCategory.CLEAN]:
        assert fixture.ground_truth.expected_outcome == "approve"
        assert fixture.ground_truth.expected_send_backs_min == 0


def test_discrepancy_fixtures_expect_at_least_one_send_back() -> None:
    by_category = load_fixtures_by_category(FIXTURES_DIR)
    for fixture in by_category[ClaimCategory.DISCREPANCY]:
        assert fixture.ground_truth.expected_send_backs_min >= 1


def test_stress_fixtures_expect_manual_review_via_a_guard() -> None:
    by_category = load_fixtures_by_category(FIXTURES_DIR)
    reasons = set()
    for fixture in by_category[ClaimCategory.STRESS]:
        assert fixture.ground_truth.expected_outcome == "needs_manual_review"
        assert fixture.ground_truth.expected_terminal_reason is not None
        reasons.add(fixture.ground_truth.expected_terminal_reason)
    # All three guard types are represented somewhere in the stress set.
    assert reasons == {"loop_guard", "step_ceiling", "budget_exceeded"}


def test_edge_fixtures_cover_the_five_documented_scenarios() -> None:
    by_category = load_fixtures_by_category(FIXTURES_DIR)
    edge_ids = {f.claim_id for f in by_category[ClaimCategory.EDGE]}
    assert edge_ids == {"CLM-026", "CLM-027", "CLM-028", "CLM-029", "CLM-030"}

    zero_damage = load_fixture_by_id(FIXTURES_DIR, "CLM-029")
    assert zero_damage.reported_damage_usd == 0

    lapsed_policy = load_fixture_by_id(FIXTURES_DIR, "CLM-030")
    assert lapsed_policy.policy.active is False


def test_load_fixture_by_id_raises_for_unknown_claim() -> None:
    with pytest.raises(FileNotFoundError):
        load_fixture_by_id(FIXTURES_DIR, "CLM-DOES-NOT-EXIST")


def test_repair_cost_benchmarks_cover_every_damage_category() -> None:
    benchmarks = load_repair_cost_benchmarks(BENCHMARKS_PATH)
    assert set(benchmarks) == set(DamageCategory)
    for bucket in benchmarks.values():
        assert bucket.low_usd < bucket.high_usd


def test_benchmark_buckets_are_monotonically_increasing() -> None:
    benchmarks = load_repair_cost_benchmarks(BENCHMARKS_PATH)
    order = [
        DamageCategory.MINOR,
        DamageCategory.MODERATE,
        DamageCategory.MAJOR,
        DamageCategory.TOTAL_LOSS,
    ]
    highs = [benchmarks[k].high_usd for k in order]
    assert highs == sorted(highs)
