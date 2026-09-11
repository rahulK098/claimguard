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

### Changed
- Project renamed **Casefile → ClaimGuard** across the codebase: the `casefile` package is now `claimguard` (`src/claimguard`), the `CASEFILE_*` env var prefix is now `CLAIMGUARD_*`, and every doc, Docker asset, and test reference was updated to match. The mock claims-system service (`claims-system` / `claims_system`) is unaffected — that name describes the insurer's system of record, not the project.

<!-- This repo is local-only (no remote); compare links are intentionally omitted. -->
