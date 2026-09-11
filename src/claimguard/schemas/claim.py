"""Claim input and synthetic fixture schemas.

A ``ClaimFixture`` is everything one synthetic test claim needs: the policy
record and prior-claim history the mock claims system will serve, the raw
documents the Extractor has to read, and the ground truth this claim is
graded against. It is the single source of truth for both the orchestrator's
input and the mock claims system's seed data (see Phase 2).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from claimguard.schemas.state import TerminalReason


class DocumentType(StrEnum):
    POLICE_REPORT = "police_report"
    REPAIR_ESTIMATE = "repair_estimate"
    ADJUSTER_NOTES = "adjuster_notes"
    INCIDENT_DESCRIPTION = "incident_description"
    MEDICAL_REPORT = "medical_report"


class DamageCategory(StrEnum):
    """Severity bucket the Extractor assigns; keys into repair_costs.json."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    TOTAL_LOSS = "total_loss"


class ClaimDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    doc_type: DocumentType
    text: str = Field(min_length=1, description="Structured text standing in for a scanned form.")


class PolicyRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    policy_number: str
    holder_name: str
    coverage_limit_usd: float = Field(gt=0)
    deductible_usd: float = Field(ge=0)
    active: bool = True
    effective_date: date
    expiration_date: date

    @model_validator(mode="after")
    def _dates_ordered(self) -> PolicyRecord:
        if self.expiration_date <= self.effective_date:
            raise ValueError("expiration_date must be after effective_date")
        return self


class ClaimantInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    claimant_id: str
    name: str


class PriorClaimStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    OPEN = "open"


class PriorClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    filed_date: date
    amount_usd: float = Field(ge=0)
    status: PriorClaimStatus


class ClaimCategory(StrEnum):
    """Fixture category — drives the eval-set composition in docs/data-model.md."""

    CLEAN = "clean"
    DISCREPANCY = "discrepancy"
    STRESS = "stress"
    EDGE = "edge"


class ClaimOutcome(StrEnum):
    """The vocabulary a Reviewer decision, and ground truth, are expressed in."""

    APPROVE = "approve"
    DENY = "deny"
    NEEDS_INFO = "needs_info"
    MANUAL_REVIEW = "needs_manual_review"


class GroundTruth(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_outcome: ClaimOutcome
    expected_send_backs_min: int = Field(default=0, ge=0, le=2)
    expected_terminal_reason: TerminalReason | None = None
    notes: str = ""


class ClaimFixture(BaseModel):
    """One synthetic claim: everything the graph and the mock claims system need."""

    model_config = ConfigDict(frozen=True)

    claim_id: str
    category: ClaimCategory
    policy: PolicyRecord
    claimant: ClaimantInfo
    prior_claims: list[PriorClaim] = Field(default_factory=list)
    documents: list[ClaimDocument] = Field(min_length=1, max_length=3)
    reported_damage_usd: float = Field(ge=0)
    ground_truth: GroundTruth
