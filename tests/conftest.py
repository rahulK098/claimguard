"""Shared fixtures.

Everything here must work with no API key, no Docker and no network.
"""

from pathlib import Path

import pytest

from claimguard.config import Settings
from claims_system.config import Settings as ClaimsSystemSettings

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "data" / "claims"
BENCHMARKS_PATH = REPO_ROOT / "data" / "benchmarks" / "repair_costs.json"

# Shared across both services' test settings so tests that mint an approval
# with one and verify it with the other exercise a real agreement, not a
# coincidence.
TEST_APPROVAL_SECRET = "test-secret"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointed at a throwaway SQLite file with tight, test-friendly ceilings."""
    return Settings(
        db_path=tmp_path / "claimguard.db",
        fixtures_dir=FIXTURES_DIR,
        approval_secret=TEST_APPROVAL_SECRET,
        claims_system_url="http://claims-system.test",
    )


@pytest.fixture
def claims_system_settings(tmp_path: Path) -> ClaimsSystemSettings:
    """Settings for the mock claims system, pointed at a throwaway SQLite file."""
    return ClaimsSystemSettings(
        approval_secret=TEST_APPROVAL_SECRET,
        db_path=tmp_path / "claims_system.db",
        fixtures_dir=FIXTURES_DIR,
        benchmarks_path=BENCHMARKS_PATH,
    )
