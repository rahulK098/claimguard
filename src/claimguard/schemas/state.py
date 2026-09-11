"""Shared outcome vocabulary.

These enums are the vocabulary a *run* is graded and terminated against —
not the full LangGraph state (that lives in ``claimguard.graph``, built in
Phase 4). Keeping them here means fixtures, hand-off schemas and the graph
all speak the same terminal-outcome language without importing the graph
module.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    """Lifecycle status of one claim run."""

    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    GATE_VIOLATION = "gate_violation"


class TerminalReason(StrEnum):
    """Why a run stopped. Every non-RUNNING/AWAITING_APPROVAL status has one.

    COMPLETED / REJECTED are ordinary outcomes. Everything else is a guard
    firing — see docs/guarantees.md for the precise semantics of each.
    """

    COMPLETED = "completed"
    REJECTED = "rejected"
    STEP_CEILING = "step_ceiling"
    LLM_CALL_CEILING = "llm_call_ceiling"
    BUDGET_EXCEEDED = "budget_exceeded"
    LOOP_GUARD = "loop_guard"
    GATE_VIOLATION = "gate_violation"
