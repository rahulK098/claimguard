"""Persists recorded decisions -- the durable proof that a write did or
did not happen for a given claim.

Separate SQLite file from the orchestrator's own database (Phase 3):
these two services keep independent state on purpose, mirroring their
independent-verification relationship (see `claims_system.auth`).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from claims_system.auth import ApprovalDecision
from claims_system.schemas import ClaimDecisionRecord


class DecisionAlreadyRecordedError(Exception):
    """Raised when a second decision is submitted for an already-decided claim.

    A claim is decided exactly once — this is what "valid id accepted once"
    means: the approval token being individually valid doesn't entitle a
    second write.
    """

    def __init__(self, claim_id: str) -> None:
        super().__init__(f"a decision was already recorded for claim_id={claim_id!r}")
        self.claim_id = claim_id


class DecisionStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                claim_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                payout_usd REAL,
                actor TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get(self, claim_id: str) -> ClaimDecisionRecord | None:
        row = self._conn.execute(
            "SELECT claim_id, run_id, decision, payout_usd, actor, recorded_at "
            "FROM decisions WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            return None
        return ClaimDecisionRecord(
            claim_id=row[0],
            run_id=row[1],
            decision=ApprovalDecision(row[2]),
            payout_usd=row[3],
            actor=row[4],
            recorded_at=datetime.fromisoformat(row[5]),
        )

    def record(
        self,
        claim_id: str,
        run_id: str,
        decision: ApprovalDecision,
        payout_usd: float | None,
        actor: str,
    ) -> ClaimDecisionRecord:
        """Atomically records a decision, or raises if one already exists.

        Uses INSERT ... ON CONFLICT DO NOTHING + rowcount rather than a
        separate SELECT-then-INSERT, so two concurrent writes for the same
        claim_id can't both "see no existing row" and both succeed.
        """
        recorded_at = datetime.now(UTC)
        cursor = self._conn.execute(
            "INSERT INTO decisions (claim_id, run_id, decision, payout_usd, actor, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(claim_id) DO NOTHING",
            (claim_id, run_id, decision.value, payout_usd, actor, recorded_at.isoformat()),
        )
        self._conn.commit()
        if cursor.rowcount == 0:
            raise DecisionAlreadyRecordedError(claim_id)
        return ClaimDecisionRecord(
            claim_id=claim_id,
            run_id=run_id,
            decision=decision,
            payout_usd=payout_usd,
            actor=actor,
            recorded_at=recorded_at,
        )

    def close(self) -> None:
        self._conn.close()
