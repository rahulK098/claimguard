"""Independent verification of the human-approval token.

This is the load-bearing half of the human gate (ADR-0007, ADR-0009): the
orchestrator mints an approval token when a human approves or rejects a
claim (``claimguard.schemas.approval.mint_approval_id``); this module
re-derives the *same* HMAC from the shared secret and the request this
service actually received, and rejects anything that doesn't match.

Deliberately does not import ``claimguard.schemas.approval`` — the two
services share a secret and a wire format (documented below), not an
implementation. That is what makes "the claims system independently
re-verifies" a true statement rather than two function calls to the same
code, and it's the property `tests/integration/test_claims_system_gate.py`
exercises by minting with one module and verifying with this one.

Wire format: ``HMAC-SHA256(secret, f"{run_id}:{claim_id}:{decision}")``,
hex-encoded. ``decision`` is the literal string ``"approve"`` or
``"reject"``.
"""

from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


def verify_approval_id(
    secret: str, run_id: str, claim_id: str, decision: ApprovalDecision, approval_id: str
) -> bool:
    """True iff approval_id is the correct HMAC for this exact (run, claim, decision)."""
    expected = hmac.new(
        secret.encode(), f"{run_id}:{claim_id}:{decision.value}".encode(), hashlib.sha256
    ).hexdigest()
    # Constant-time comparison -- an approval token is a bearer credential;
    # a naive `==` would leak timing information about how many leading
    # hex characters matched.
    return hmac.compare_digest(expected, approval_id)
