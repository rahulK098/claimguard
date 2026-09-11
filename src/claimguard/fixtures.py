"""Loads the synthetic claim fixtures used as this project's eval set.

Fixtures live under ``data/claims/*.json`` as flat ``ClaimFixture``
documents (see docs/data-model.md for the composition: 10 clean, 10
discrepancy, 5 stress, 5 edge).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel

from claimguard.schemas.claim import ClaimCategory, ClaimFixture, DamageCategory


def load_fixture(path: Path) -> ClaimFixture:
    return ClaimFixture.model_validate_json(path.read_text(encoding="utf-8"))


def iter_fixtures(fixtures_dir: Path) -> Iterator[ClaimFixture]:
    for path in sorted(fixtures_dir.glob("*.json")):
        yield load_fixture(path)


def load_all_fixtures(fixtures_dir: Path) -> list[ClaimFixture]:
    return list(iter_fixtures(fixtures_dir))


def load_fixtures_by_category(fixtures_dir: Path) -> dict[ClaimCategory, list[ClaimFixture]]:
    by_category: dict[ClaimCategory, list[ClaimFixture]] = {c: [] for c in ClaimCategory}
    for fixture in iter_fixtures(fixtures_dir):
        by_category[fixture.category].append(fixture)
    return by_category


def load_fixture_by_id(fixtures_dir: Path, claim_id: str) -> ClaimFixture:
    for fixture in iter_fixtures(fixtures_dir):
        if fixture.claim_id == claim_id:
            return fixture
    raise FileNotFoundError(f"no fixture with claim_id={claim_id!r} under {fixtures_dir}")


class RepairCostBucket(BaseModel):
    model_config = ConfigDict(frozen=True)

    low_usd: float
    high_usd: float


_RepairCostBenchmarks = RootModel[dict[DamageCategory, RepairCostBucket]]


def load_repair_cost_benchmarks(benchmarks_path: Path) -> dict[DamageCategory, RepairCostBucket]:
    """Validated repair-cost benchmark table, keyed by DamageCategory.

    Used by the Investigator's damage-vs-repair-cost sanity check (Phase 4).
    """
    return _RepairCostBenchmarks.model_validate_json(
        benchmarks_path.read_text(encoding="utf-8")
    ).root
