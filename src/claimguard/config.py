"""Runtime configuration for the orchestrator.

Every ceiling that bounds a run lives here so it is visible in one place and
can be overridden per environment. Nothing in this file is read by an LLM;
the guards in ``claimguard.graph.guards`` consume these values directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLAIMGUARD_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM -------------------------------------------------------------
    model: str = Field(default="claude-opus-5", description="Anthropic model id for all nodes.")
    max_tokens_per_call: int = Field(
        default=4096,
        description="Hard output cap per LLM call. Bounds budget overshoot to one call's worth.",
    )

    # --- Ceilings (enforced by code in the supervisor) --------------------
    budget_usd: float = Field(default=0.50, description="Per-claim dollar ceiling.")
    max_steps: int = Field(default=12, description="Max node executions per run.")
    max_llm_calls: int = Field(default=10, description="Max LLM calls per run, retries included.")
    max_send_backs: int = Field(
        default=2, description="Max Reviewer->Investigator send-backs before forced manual review."
    )
    max_retries_per_call: int = Field(default=1, description="Retries allowed for one LLM call.")
    recursion_limit: int = Field(
        default=25, description="LangGraph backstop only; real guards fire long before this."
    )

    # --- Storage ---------------------------------------------------------
    db_path: Path = Field(default=Path("data/runtime/claimguard.db"))
    fixtures_dir: Path = Field(default=Path("data/claims"))

    # --- Integrations ----------------------------------------------------
    claims_system_url: str = Field(default="http://localhost:8001")
    approval_secret: str = Field(
        default="dev-only-change-me",
        description="Shared HMAC secret used to mint and verify approval tokens.",
    )

    # --- Tracing ---------------------------------------------------------
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="claimguard-api", alias="OTEL_SERVICE_NAME")


@lru_cache
def get_settings() -> Settings:
    return Settings()
