"""Shared fixtures.

Everything here must work with no API key, no Docker and no network.
"""

from pathlib import Path

import pytest

from claimguard.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings pointed at a throwaway SQLite file with tight, test-friendly ceilings."""
    return Settings(
        db_path=tmp_path / "claimguard.db",
        fixtures_dir=REPO_ROOT / "data" / "claims",
        approval_secret="test-secret",
        claims_system_url="http://claims-system.test",
    )
