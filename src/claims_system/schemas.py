"""Request/response shapes owned by the claims system itself.

Policy, prior-claim and benchmark data reuse ``claimguard.schemas`` types
directly (see `data.py`) — that's shared *data*, not a trust boundary.
These models are specific to this service's own decision-recording API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from claims_system.auth import ApprovalDecision


class ClaimDecisionRequest(BaseModel):
    """Body of `POST /claims/{claim_id}/decision`."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    decision: ApprovalDecision
    payout_usd: float | None = Field(default=None, ge=0)
    actor: str = Field(default="unspecified-human", min_length=1)


class ClaimDecisionRecord(BaseModel):
    """A recorded decision, as stored and as returned by both endpoints."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    run_id: str
    decision: ApprovalDecision
    payout_usd: float | None
    actor: str
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ClaimStatusResponse(BaseModel):
    """Response for `GET /claims/{claim_id}` — proves whether a write happened."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    decision: ClaimDecisionRecord | None
