"""Runtime configuration for the mock claims system.

Deliberately minimal, and deliberately does **not** import
``claimguard.config`` — the two services should be configurable
independently even though they happen to ship in the same image. The one
value that must agree between them is ``approval_secret``: both read it from
the same environment variable name (``CLAIMGUARD_APPROVAL_SECRET``, no
``CLAIMS_SYSTEM_`` prefix) because it's a *shared* secret, not a per-service
setting — see ADR-0007.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    approval_secret: str = Field(
        default="dev-only-change-me", validation_alias="CLAIMGUARD_APPROVAL_SECRET"
    )
    db_path: Path = Field(
        default=Path("data/runtime/claims_system.db"), validation_alias="CLAIMS_SYSTEM_DB_PATH"
    )
    fixtures_dir: Path = Field(default=Path("data/claims"))
    benchmarks_path: Path = Field(default=Path("data/benchmarks/repair_costs.json"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
