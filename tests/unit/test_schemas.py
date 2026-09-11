"""Schema round-trip and decision-consistency validators."""

from datetime import date

import pytest
from pydantic import ValidationError

from claimguard.schemas.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalToken,
    mint_approval_id,
)
from claimguard.schemas.claim import (
    ClaimantInfo,
    ClaimCategory,
    ClaimDocument,
    ClaimFixture,
    ClaimOutcome,
    DocumentType,
    GroundTruth,
    PolicyRecord,
)
from claimguard.schemas.handoffs import (
    DamageCategory,
    ExtractionConfidence,
    ExtractorOutput,
    InvestigatorOutput,
    PolicyCheck,
    PriorClaimsCheck,
    RepairCostAssessment,
    ReviewDecision,
    ReviewerOutput,
    SendBackReason,
)


def _policy(**overrides: object) -> PolicyRecord:
    defaults: dict[str, object] = dict(
        policy_number="POL-1",
        holder_name="Test Holder",
        coverage_limit_usd=10000,
        deductible_usd=500,
        effective_date=date(2025, 1, 1),
        expiration_date=date(2026, 1, 1),
    )
    defaults.update(overrides)
    return PolicyRecord.model_validate(defaults)


class TestPolicyRecord:
    def test_valid_dates_round_trip(self) -> None:
        p = _policy()
        assert PolicyRecord.model_validate_json(p.model_dump_json()) == p

    def test_expiration_before_effective_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(effective_date=date(2026, 1, 1), expiration_date=date(2025, 1, 1))

    def test_expiration_equal_effective_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _policy(effective_date=date(2026, 1, 1), expiration_date=date(2026, 1, 1))


class TestClaimFixtureRoundTrip:
    def _fixture(self) -> ClaimFixture:
        return ClaimFixture(
            claim_id="CLM-TEST",
            category=ClaimCategory.CLEAN,
            policy=_policy(),
            claimant=ClaimantInfo(claimant_id="CLT-1", name="Test Claimant"),
            documents=[
                ClaimDocument(doc_id="D1", doc_type=DocumentType.INCIDENT_DESCRIPTION, text="x"),
            ],
            reported_damage_usd=100,
            ground_truth=GroundTruth(expected_outcome=ClaimOutcome.APPROVE),
        )

    def test_round_trip(self) -> None:
        f = self._fixture()
        assert ClaimFixture.model_validate_json(f.model_dump_json()) == f

    def test_documents_must_be_nonempty(self) -> None:
        with pytest.raises(ValidationError):
            ClaimFixture(
                claim_id="CLM-EMPTY",
                category=ClaimCategory.EDGE,
                policy=_policy(),
                claimant=ClaimantInfo(claimant_id="CLT-1", name="Test"),
                documents=[],
                reported_damage_usd=0,
                ground_truth=GroundTruth(expected_outcome=ClaimOutcome.DENY),
            )

    def test_documents_capped_at_three(self) -> None:
        docs = [
            ClaimDocument(doc_id=f"D{i}", doc_type=DocumentType.ADJUSTER_NOTES, text="x")
            for i in range(4)
        ]
        with pytest.raises(ValidationError):
            ClaimFixture(
                claim_id="CLM-TOOMANY",
                category=ClaimCategory.EDGE,
                policy=_policy(),
                claimant=ClaimantInfo(claimant_id="CLT-1", name="Test"),
                documents=docs,
                reported_damage_usd=0,
                ground_truth=GroundTruth(expected_outcome=ClaimOutcome.DENY),
            )


class TestExtractorOutput:
    def test_round_trip(self) -> None:
        out = ExtractorOutput(
            claim_id="CLM-1",
            policy_number="POL-1",
            claimant_id="CLT-1",
            incident_description="Rear-ended at a light.",
            damage_category=DamageCategory.MINOR,
            damage_estimate_usd=1200,
            extraction_confidence=ExtractionConfidence.HIGH,
        )
        assert ExtractorOutput.model_validate_json(out.model_dump_json()) == out


class TestInvestigatorOutput:
    def _assessment(self, **overrides: object) -> RepairCostAssessment:
        defaults: dict[str, object] = dict(
            benchmark_low_usd=500, benchmark_high_usd=3000,
            reported_damage_usd=2000, within_tolerance=True,
        )
        defaults.update(overrides)
        return RepairCostAssessment.model_validate(defaults)

    def test_benchmark_high_below_low_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._assessment(benchmark_low_usd=3000, benchmark_high_usd=500)

    def test_prior_claims_check_requires_reason_when_flagged(self) -> None:
        with pytest.raises(ValidationError):
            PriorClaimsCheck(prior_claim_count=2, flagged=True, flag_reason=None)

    def test_prior_claims_check_rejects_reason_when_not_flagged(self) -> None:
        with pytest.raises(ValidationError):
            PriorClaimsCheck(prior_claim_count=0, flagged=False, flag_reason="shouldn't be here")

    def test_round_trip(self) -> None:
        out = InvestigatorOutput(
            claim_id="CLM-1",
            policy_check=PolicyCheck(
                policy_active=True, within_coverage_limit=True, coverage_limit_usd=10000
            ),
            prior_claims_check=PriorClaimsCheck(prior_claim_count=0, flagged=False),
            repair_cost_assessment=self._assessment(),
            summary="Looks fine.",
        )
        assert InvestigatorOutput.model_validate_json(out.model_dump_json()) == out


class TestReviewerOutput:
    def test_send_back_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            ReviewerOutput(
                claim_id="CLM-1",
                decision=ReviewDecision.SEND_BACK,
                send_back_reason=None,
                recommendation_summary="needs another look",
            )

    def test_reason_forbidden_unless_send_back(self) -> None:
        with pytest.raises(ValidationError):
            ReviewerOutput(
                claim_id="CLM-1",
                decision=ReviewDecision.APPROVE,
                send_back_reason=SendBackReason.INSUFFICIENT_DETAIL,
                recommended_payout_usd=100,
                recommendation_summary="approved",
            )

    def test_approve_requires_payout(self) -> None:
        with pytest.raises(ValidationError):
            ReviewerOutput(
                claim_id="CLM-1",
                decision=ReviewDecision.APPROVE,
                recommended_payout_usd=None,
                recommendation_summary="approved",
            )

    def test_payout_forbidden_unless_approve(self) -> None:
        with pytest.raises(ValidationError):
            ReviewerOutput(
                claim_id="CLM-1",
                decision=ReviewDecision.DENY,
                recommended_payout_usd=500,
                recommendation_summary="denied",
            )

    def test_valid_send_back_round_trips(self) -> None:
        out = ReviewerOutput(
            claim_id="CLM-1",
            decision=ReviewDecision.SEND_BACK,
            send_back_reason=SendBackReason.DAMAGE_VARIANCE_UNRESOLVED,
            recommendation_summary="damage estimate needs re-checking",
        )
        assert ReviewerOutput.model_validate_json(out.model_dump_json()) == out

    def test_valid_approve_round_trips(self) -> None:
        out = ReviewerOutput(
            claim_id="CLM-1",
            decision=ReviewDecision.APPROVE,
            recommended_payout_usd=1500,
            recommendation_summary="approved at estimate",
        )
        assert ReviewerOutput.model_validate_json(out.model_dump_json()) == out


class TestApproval:
    def test_mint_is_deterministic(self) -> None:
        a = mint_approval_id("secret", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        b = mint_approval_id("secret", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        assert a == b

    def test_mint_differs_by_decision(self) -> None:
        approve = mint_approval_id("secret", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        reject = mint_approval_id("secret", "run-1", "CLM-1", ApprovalDecision.REJECT)
        assert approve != reject

    def test_mint_differs_by_secret(self) -> None:
        a = mint_approval_id("secret-a", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        b = mint_approval_id("secret-b", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        assert a != b

    def test_mint_differs_by_run_or_claim(self) -> None:
        base = mint_approval_id("secret", "run-1", "CLM-1", ApprovalDecision.APPROVE)
        other_run = mint_approval_id("secret", "run-2", "CLM-1", ApprovalDecision.APPROVE)
        other_claim = mint_approval_id("secret", "run-1", "CLM-2", ApprovalDecision.APPROVE)
        assert base != other_run
        assert base != other_claim

    def test_token_mint_matches_bare_function(self) -> None:
        request = ApprovalRequest(decision=ApprovalDecision.APPROVE, actor="adjuster-1")
        token = ApprovalToken.mint("secret", "run-1", "CLM-1", request)
        assert token.approval_id == mint_approval_id(
            "secret", "run-1", "CLM-1", ApprovalDecision.APPROVE
        )
        assert token.actor == "adjuster-1"
