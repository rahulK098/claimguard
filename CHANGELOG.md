# Changelog

All notable changes to this project are documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project bootstrap: `pyproject.toml` (uv-managed), lockfile, `.python-version` (3.12).
- `Dockerfile` (multi-stage, non-root runtime) and `docker-compose.yml` (`api`, `claims-system`, `jaeger` services, shared `claimguard-data` volume).
- `env.example` — configuration template covering the model, every ceiling, the approval secret, storage and tracing settings.
- `src/claimguard` package skeleton: `config.py` (`Settings`, all ceilings), `api/app.py` (FastAPI factory with `/healthz`).
- `src/claims_system` package skeleton: FastAPI app with `/healthz`.
- Test scaffolding: `tests/{unit,integration,scenario}`, shared `conftest.py` fixtures, health-check integration tests.
- Documentation skeleton: `docs/README.md` index, `docs/implementation-plan.md` (phased plan + ship gate), `docs/tech-stack.md`, `docs/architecture.md` (service topology + agent graph diagrams), `docs/adr/` (template, index, ADR-0001 LangGraph, ADR-0002 SQLite, ADR-0009 Docker topology).
- `README.md`, `LICENSE` (MIT), `.gitignore`, `.dockerignore`.

**Phase 1 — schemas, fixtures, pricing:**
- Typed hand-off contracts (`src/claimguard/schemas/`): `claim.py` (`ClaimFixture`, `PolicyRecord`, `ClaimantInfo`, `PriorClaim`, `ClaimDocument`, `GroundTruth`), `handoffs.py` (`ExtractorOutput`, `InvestigatorOutput`, `ReviewerOutput`, `LLMFailure`, with cross-field validators enforcing decision consistency), `state.py` (`RunStatus`, `TerminalReason`), `approval.py` (`ApprovalDecision`/`ApprovalRequest`/`ApprovalToken`, HMAC `mint_approval_id`).
- `src/claimguard/llm/pricing.py` — per-model $/MTok table (Opus 5, Sonnet 5, Haiku 4.5) and `compute_cost_usd`.
- `src/claimguard/fixtures.py` — fixture loader (`load_all_fixtures`, `load_fixtures_by_category`, `load_fixture_by_id`, `load_repair_cost_benchmarks`).
- 30 synthetic claim fixtures in `data/claims/*.json` (10 clean, 10 discrepancy, 5 stress, 5 edge) and `data/benchmarks/repair_costs.json`.
- `tests/unit/{test_schemas,test_fixtures,test_pricing}.py` — 40 tests covering round-trips, validator rejection paths, fixture-set composition invariants, and pricing math.
- `docs/data-model.md`, ADR-0003 (typed hand-offs via structured outputs), ADR-0010 (synthetic fixture eval set).

### Changed
- Project renamed **Casefile → ClaimGuard** across the codebase: the `casefile` package is now `claimguard` (`src/claimguard`), the `CASEFILE_*` env var prefix is now `CLAIMGUARD_*`, and every doc, Docker asset, and test reference was updated to match. The mock claims-system service (`claims-system` / `claims_system`) is unaffected — that name describes the insurer's system of record, not the project.

<!-- This repo has a remote (origin -> github.com/rahulK098/claimguard); compare links are omitted here since docs/ itself is not committed. -->
