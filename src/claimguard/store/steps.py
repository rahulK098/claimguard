"""Repository for the `llm_calls` table -- what `RecordingClient` writes to
and `ReplayClient` reads from.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmCallRecord:
    run_id: str
    call_index: int
    node: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_priced: bool
    stop_reason: str | None
    latency_ms: float | None
    response: str | None
    error: str | None


class LlmCallStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def next_call_index(self, run_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(call_index), -1) + 1 FROM llm_calls WHERE run_id = ?", (run_id,)
        ).fetchone()
        return int(row[0])

    def record_llm_call(
        self,
        *,
        run_id: str,
        call_index: int,
        node: str,
        provider: str,
        model: str,
        request: dict[str, object],
        response: str | None,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cost_priced: bool,
        stop_reason: str | None,
        latency_ms: float | None,
        error: str | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO llm_calls (run_id, call_index, node, provider, model, request_json, "
            "response_json, input_tokens, output_tokens, cost_usd, cost_priced, stop_reason, "
            "latency_ms, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                call_index,
                node,
                provider,
                model,
                json.dumps(request),
                response,
                input_tokens,
                output_tokens,
                cost_usd,
                1 if cost_priced else 0,
                stop_reason,
                latency_ms,
                error,
            ),
        )
        self._conn.commit()

    def get_llm_calls(self, run_id: str) -> list[LlmCallRecord]:
        rows = self._conn.execute(
            "SELECT run_id, call_index, node, provider, model, input_tokens, output_tokens, "
            "cost_usd, cost_priced, stop_reason, latency_ms, response_json, error "
            "FROM llm_calls WHERE run_id = ? ORDER BY call_index",
            (run_id,),
        ).fetchall()
        return [
            LlmCallRecord(
                run_id=r[0],
                call_index=r[1],
                node=r[2],
                provider=r[3],
                model=r[4],
                input_tokens=r[5],
                output_tokens=r[6],
                cost_usd=r[7],
                cost_priced=bool(r[8]),
                stop_reason=r[9],
                latency_ms=r[10],
                response=r[11],
                error=r[12],
            )
            for r in rows
        ]
