"""FastAPI application for the mock claims system of record.

Endpoints:
  GET  /healthz
  GET  /policies/{policy_number}
  GET  /claimants/{claimant_id}/prior-claims
  GET  /benchmarks/repair-cost
  GET  /claims/{claim_id}                  -- proves whether a write happened
  POST /claims/{claim_id}/decision         -- HMAC-gated (X-Approval-Id header)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from claimguard.fixtures import RepairCostBucket
from claimguard.schemas.claim import DamageCategory, PolicyRecord, PriorClaim
from claims_system import __version__
from claims_system.auth import verify_approval_id
from claims_system.config import Settings, get_settings
from claims_system.data import ClaimsSystemData
from claims_system.schemas import ClaimDecisionRecord, ClaimDecisionRequest, ClaimStatusResponse
from claims_system.store import DecisionAlreadyRecordedError, DecisionStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Populated by the lifespan handler on startup. Held in closures rather
    # than on `app.state` so the dependency functions below are precisely
    # typed for mypy --strict, instead of reading an untyped attribute bag.
    runtime: dict[str, object] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        runtime["data"] = ClaimsSystemData(settings.fixtures_dir, settings.benchmarks_path)
        runtime["store"] = DecisionStore(settings.db_path)
        try:
            yield
        finally:
            store = runtime.get("store")
            if isinstance(store, DecisionStore):
                store.close()

    app = FastAPI(
        title="Claims System (mock)",
        version=__version__,
        lifespan=lifespan,
        description=(
            "Mocked system of record. Read endpoints serve policy, prior-claim and "
            "repair-benchmark data drawn from the same fixtures the orchestrator's "
            "eval set uses. The decision endpoint independently re-verifies the "
            "human-approval token and rejects any write that doesn't carry a valid "
            "one -- see docs/adr/0007-hmac-approval-gate.md."
        ),
    )

    def get_data() -> ClaimsSystemData:
        data = runtime["data"]
        assert isinstance(data, ClaimsSystemData)
        return data

    def get_store() -> DecisionStore:
        store = runtime["store"]
        assert isinstance(store, DecisionStore)
        return store

    DataDep = Annotated[ClaimsSystemData, Depends(get_data)]
    StoreDep = Annotated[DecisionStore, Depends(get_store)]

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "claims-system", "version": __version__}

    @app.get("/policies/{policy_number}", response_model=PolicyRecord, tags=["read"])
    def get_policy(policy_number: str, data: DataDep) -> PolicyRecord:
        policy = data.get_policy(policy_number)
        if policy is None:
            raise HTTPException(404, f"unknown policy_number {policy_number!r}")
        return policy

    @app.get(
        "/claimants/{claimant_id}/prior-claims",
        response_model=list[PriorClaim],
        tags=["read"],
    )
    def get_prior_claims(claimant_id: str, data: DataDep) -> list[PriorClaim]:
        priors = data.get_prior_claims(claimant_id)
        if priors is None:
            raise HTTPException(404, f"unknown claimant_id {claimant_id!r}")
        return priors

    @app.get(
        "/benchmarks/repair-cost",
        response_model=dict[DamageCategory, RepairCostBucket],
        tags=["read"],
    )
    def get_repair_cost_benchmarks(data: DataDep) -> dict[DamageCategory, RepairCostBucket]:
        return data.benchmarks

    @app.get("/claims/{claim_id}", response_model=ClaimStatusResponse, tags=["decision"])
    def get_claim_status(claim_id: str, data: DataDep, store: StoreDep) -> ClaimStatusResponse:
        if not data.is_known_claim(claim_id):
            raise HTTPException(404, f"unknown claim_id {claim_id!r}")
        return ClaimStatusResponse(claim_id=claim_id, decision=store.get(claim_id))

    @app.post(
        "/claims/{claim_id}/decision",
        response_model=ClaimDecisionRecord,
        status_code=201,
        tags=["decision"],
    )
    def post_decision(
        claim_id: str,
        body: ClaimDecisionRequest,
        data: DataDep,
        store: StoreDep,
        x_approval_id: Annotated[str | None, Header(alias="X-Approval-Id")] = None,
    ) -> ClaimDecisionRecord:
        if not data.is_known_claim(claim_id):
            raise HTTPException(404, f"unknown claim_id {claim_id!r}")
        if not x_approval_id or not verify_approval_id(
            settings.approval_secret, body.run_id, claim_id, body.decision, x_approval_id
        ):
            raise HTTPException(403, "missing or invalid X-Approval-Id")
        try:
            return store.record(claim_id, body.run_id, body.decision, body.payout_usd, body.actor)
        except DecisionAlreadyRecordedError as exc:
            raise HTTPException(409, str(exc)) from exc

    return app


# Module-level instance for `uvicorn claims_system.app:app` (matches
# docker-compose.yml's non-factory invocation). Cheap to construct: fixture
# and database loading happens in the lifespan handler above, not here.
app = create_app()
