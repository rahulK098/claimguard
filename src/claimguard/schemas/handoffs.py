"""Typed hand-offs between agent nodes.

Every field an agent produces that another node or the Supervisor reads is
defined here as a Pydantic model with enum-constrained decision fields. No
free text crosses a node boundary as a *decision* — only as supporting
narrative (``summary``, ``recommendation_summary``, ...). The Supervisor's
routing functions (Phase 4) read only the enum/counter fields on these
models, never the narrative text.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from claimguard.schemas.claim import DamageCategory


class ExtractionConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractorOutput(BaseModel):
    """Extractor: raw claim documents -> typed fields."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    policy_number: str
    claimant_id: str
    incident_date: date | None = None
    incident_description: str = Field(min_length=1)
    damage_category: DamageCategory
    damage_estimate_usd: float = Field(ge=0)
    extraction_confidence: ExtractionConfidence
    missing_fields: list[str] = Field(default_factory=list)


class PolicyCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_active: bool
    within_coverage_limit: bool
    coverage_limit_usd: float = Field(ge=0)


class PriorClaimsCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    prior_claim_count: int = Field(ge=0)
    flagged: bool
    flag_reason: str | None = None

    @model_validator(mode="after")
    def _flag_reason_matches_flag(self) -> PriorClaimsCheck:
        if self.flagged and not self.flag_reason:
            raise ValueError("flag_reason is required when flagged is True")
        if not self.flagged and self.flag_reason:
            raise ValueError("flag_reason must be empty when flagged is False")
        return self


class RepairCostAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_low_usd: float = Field(ge=0)
    benchmark_high_usd: float = Field(ge=0)
    reported_damage_usd: float = Field(ge=0)
    within_tolerance: bool

    @model_validator(mode="after")
    def _benchmark_ordered(self) -> RepairCostAssessment:
        if self.benchmark_high_usd < self.benchmark_low_usd:
            raise ValueError("benchmark_high_usd must be >= benchmark_low_usd")
        return self


class InvestigatorOutput(BaseModel):
    """Investigator: prior claims, policy limits, damage-vs-repair-cost sanity check.

    Pure findings only — the Investigator does not decide send-back; that
    decision (and its typed reason) belongs to the Reviewer.
    """

    model_config = ConfigDict(frozen=True)

    claim_id: str
    policy_check: PolicyCheck
    prior_claims_check: PriorClaimsCheck
    repair_cost_assessment: RepairCostAssessment
    summary: str = Field(min_length=1)


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    NEEDS_INFO = "needs_info"
    SEND_BACK = "send_back"


class SendBackReason(StrEnum):
    """Typed reason a Reviewer sends a claim back to the Investigator.

    Never free text — this is what keeps the send-back path auditable.
    """

    DAMAGE_VARIANCE_UNRESOLVED = "damage_variance_unresolved"
    PRIOR_CLAIM_FLAG_UNRESOLVED = "prior_claim_flag_unresolved"
    INSUFFICIENT_DETAIL = "insufficient_detail"
    POLICY_CHECK_INCOMPLETE = "policy_check_incomplete"


class ReviewerOutput(BaseModel):
    """Reviewer: sanity-checks the Investigator's case; may send it back."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    decision: ReviewDecision
    send_back_reason: SendBackReason | None = None
    recommended_payout_usd: float | None = Field(default=None, ge=0)
    recommendation_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def _decision_fields_consistent(self) -> ReviewerOutput:
        if self.decision == ReviewDecision.SEND_BACK and self.send_back_reason is None:
            raise ValueError("send_back_reason is required when decision is SEND_BACK")
        if self.decision != ReviewDecision.SEND_BACK and self.send_back_reason is not None:
            raise ValueError("send_back_reason must be unset unless decision is SEND_BACK")
        if self.decision == ReviewDecision.APPROVE and self.recommended_payout_usd is None:
            raise ValueError("recommended_payout_usd is required when decision is APPROVE")
        if self.decision != ReviewDecision.APPROVE and self.recommended_payout_usd is not None:
            raise ValueError("recommended_payout_usd must be unset unless decision is APPROVE")
        return self


class LLMFailureKind(StrEnum):
    """Why a call to the model produced no usable structured output.

    Counts as an LLM call against the ceiling either way; routes the run to
    NEEDS_MANUAL_REVIEW rather than crashing (see docs/guarantees.md).
    """

    MAX_TOKENS = "max_tokens"
    REFUSAL = "refusal"
    SCHEMA_VALIDATION = "schema_validation"


class LLMFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    node: Literal["extractor", "investigator", "reviewer"]
    kind: LLMFailureKind
    detail: str = Field(min_length=1)
