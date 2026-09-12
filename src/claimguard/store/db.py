"""SQLite connection + schema for the orchestrator's own state.

One file, WAL mode, four tables (`runs`, `steps`, `llm_calls`, `approvals`)
plus whatever tables LangGraph's `SqliteSaver` adds on top in the same file
(Phase 4) -- see docs/adr/0002-sqlite-state-store.md.

Only `llm_calls` has a repository (`store.steps.LlmCallStore`) as of Phase 3;
`runs`/`steps`/`approvals` get theirs in Phase 4/5 when the graph and API
exist to populate them. The schema is created now so it's all in one place
and versioned from the start rather than accreting ad hoc.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    terminal_reason TEXT,
    step_count INTEGER NOT NULL DEFAULT 0,
    llm_calls INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    node_path_json TEXT NOT NULL DEFAULT '[]',
    source_run_id TEXT,
    ground_truth TEXT,
    recommendation TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    node TEXT NOT NULL,
    entered_at TEXT NOT NULL,
    exited_at TEXT,
    state_before_json TEXT,
    state_after_json TEXT,
    decision_json TEXT,
    PRIMARY KEY (run_id, step_index)
);

CREATE TABLE IF NOT EXISTS llm_calls (
    run_id TEXT NOT NULL,
    call_index INTEGER NOT NULL,
    node TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    cost_priced INTEGER NOT NULL DEFAULT 1,
    stop_reason TEXT,
    latency_ms REAL,
    error TEXT,
    PRIMARY KEY (run_id, call_index)
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
