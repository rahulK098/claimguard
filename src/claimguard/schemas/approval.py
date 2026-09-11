"""Human approval gate: shapes and the token-minting side of the HMAC check.

The orchestrator mints an approval token here when a human approves or
rejects a paused claim (Phase 5's ``POST /claims/{id}/approve`` endpoint).
The mock claims system (Phase 2, ``claims_system.auth``) does **not** import
this module — it independently recomputes the same HMAC from the shared
secret and the request it actually received. Sharing the token *shape* is
fine; the two services deliberately do not share the *verification* code
path, so the gate is a real trust boundary rather than one service trusting
the other's say-so (see ADR-0007, ADR-0009).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


def _signing_message(run_id: str, claim_id: str, decision: ApprovalDecision) -> bytes:
    # Fixed field order and separator so the message is unambiguous — an
    # approval for one (run_id, claim_id, decision) triple can never be
    # replayed against a different one.
    return f"{run_id}:{claim_id}:{decision.value}".encode()


def mint_approval_id(
    secret: str, run_id: str, claim_id: str, decision: ApprovalDecision
) -> str:
    """HMAC-SHA256 of (run_id, claim_id, decision) under the shared secret."""
    return hmac.new(
        secret.encode(), _signing_message(run_id, claim_id, decision), hashlib.sha256
    ).hexdigest()


class ApprovalRequest(BaseModel):
    """What a human submits to `POST /claims/{claim_id}/approve|reject`."""

    model_config = ConfigDict(frozen=True)

    decision: ApprovalDecision
    actor: str = Field(default="unspecified-human", min_length=1)


class ApprovalToken(BaseModel):
    """A minted, persisted approval — what the `approvals` table stores."""

    model_config = ConfigDict(frozen=True)

    approval_id: str
    run_id: str
    claim_id: str
    decision: ApprovalDecision
    actor: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def mint(
        cls, secret: str, run_id: str, claim_id: str, request: ApprovalRequest
    ) -> ApprovalToken:
        approval_id = mint_approval_id(secret, run_id, claim_id, request.decision)
        return cls(
            approval_id=approval_id,
            run_id=run_id,
            claim_id=claim_id,
            decision=request.decision,
            actor=request.actor,
        )
