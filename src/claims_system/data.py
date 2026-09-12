"""Seed data for the mock claims system, loaded from the same fixtures the
orchestrator's eval set uses (`data/claims/*.json`).

This is the shared *read* data both services legitimately agree on — the
policy record and prior-claim history a fixture describes. It is not the
trust boundary; see `claims_system.auth` for the part that is.
"""

from __future__ import annotations

from pathlib import Path

from claimguard.fixtures import RepairCostBucket, load_all_fixtures, load_repair_cost_benchmarks
from claimguard.schemas.claim import DamageCategory, PolicyRecord, PriorClaim


class ClaimsSystemData:
    def __init__(self, fixtures_dir: Path, benchmarks_path: Path) -> None:
        fixtures = load_all_fixtures(fixtures_dir)

        self._known_claim_ids: set[str] = {f.claim_id for f in fixtures}
        self._policies_by_number: dict[str, PolicyRecord] = {
            f.policy.policy_number: f.policy for f in fixtures
        }
        self._prior_claims_by_claimant: dict[str, list[PriorClaim]] = {
            f.claimant.claimant_id: f.prior_claims for f in fixtures
        }
        self.benchmarks: dict[DamageCategory, RepairCostBucket] = load_repair_cost_benchmarks(
            benchmarks_path
        )

    def is_known_claim(self, claim_id: str) -> bool:
        return claim_id in self._known_claim_ids

    def get_policy(self, policy_number: str) -> PolicyRecord | None:
        return self._policies_by_number.get(policy_number)

    def get_prior_claims(self, claimant_id: str) -> list[PriorClaim] | None:
        """None means the claimant is unknown; [] means known with no prior claims."""
        return self._prior_claims_by_claimant.get(claimant_id)
