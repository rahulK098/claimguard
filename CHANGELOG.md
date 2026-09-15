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

**Phase 2 — mock claims system service:**
- `src/claims_system/config.py` — settings reading the shared `CLAIMGUARD_APPROVAL_SECRET` (no `CLAIMS_SYSTEM_` prefix, since it's a secret shared with the orchestrator, not a per-service one) and a `CLAIMS_SYSTEM_DB_PATH`.
- `src/claims_system/auth.py` — independent HMAC verification of the approval token (`verify_approval_id`, constant-time comparison via `hmac.compare_digest`). Deliberately does not import `claimguard.schemas.approval` — same wire protocol, two separately-written implementations, so the gate is a real trust boundary, not a shared function call. See ADR-0007.
- `src/claims_system/data.py` — read-only lookups (`ClaimsSystemData`) seeded from the same 30 fixtures: policies by number, prior claims by claimant, repair-cost benchmarks by damage category.
- `src/claims_system/store.py` — `DecisionStore`, its own SQLite file recording decisions; atomic first-write-wins via `INSERT ... ON CONFLICT DO NOTHING`, so a second, independently-valid approval token still can't write a second decision for the same claim (`DecisionAlreadyRecordedError` -> `409`).
- `src/claims_system/schemas.py` — `ClaimDecisionRequest`/`ClaimDecisionRecord`/`ClaimStatusResponse`.
- `src/claims_system/app.py` — wired into a full FastAPI app: `GET /policies/{policy_number}`, `GET /claimants/{claimant_id}/prior-claims`, `GET /benchmarks/repair-cost`, `GET /claims/{claim_id}` (proves whether a write happened), `POST /claims/{claim_id}/decision` (`X-Approval-Id`-gated: `403` missing/forged, `409` already-decided, `404` unknown claim, `201` on success).
- `src/claimguard/tools/claims_system.py` — the async `ClaimsSystemClient` httpx wrapper the graph's Investigator/writeback nodes will use in Phase 4.
- `scripts/export_openapi.py` and both `docs/api/openapi-*.json`.
- 44 new tests (`tests/unit/test_claims_system_{auth,store,data}.py`, `tests/integration/test_claims_system_{endpoints,gate,client}.py`) — including the cross-module mint-with-one/verify-with-the-other check, every gate rejection path (missing header, forged header, wrong claim, wrong decision, unknown claim, already-decided), and the full round trip through Docker (verified live: `docker compose up`, minted a real token inside the container, `201` then `409` on retry).
- `docs/api/README.md`, ADR-0007 (HMAC approval token as a structural human gate).

**Phase 3 — LLM client layer, now multi-provider:**
- `llm/client.py` — the provider-agnostic `LLMClient` protocol and generic `LLMResult[T]`; `raw_text` is defined identically across every provider (exactly the JSON that validates as `output_model`), which is what makes replay provider-independent.
- `llm/json_extraction.py` — the shared JSON-extraction + Pydantic-validation path (`parse_structured_response`, `extract_json_object`, `build_schema_instructions`) every provider adapter converges on, regardless of native structured-output support.
- `llm/provider_settings.py` — `ProviderSettings`, reading the operator's existing env var convention (`LLM_PROVIDER`, `AZURE_OPENAI_KEY`, `GROQ_API_KEY`, ...) rather than the usual `CLAIMGUARD_` prefix, so an existing `.env` just works.
- `llm/providers/`: `AnthropicClient` (native SDK, `output_config.format: json_schema`), `OpenAICompatibleClient` + `AzureOpenAIClient` (key rotation across two keys) covering Azure/OpenRouter/Groq/DeepSeek, `GeminiClient` (native `responseSchema`), `OllamaClient` (local, always last in the chain, no credentials needed). Every adapter tries native structured output first and degrades to a prompt-embedded-schema request on any error.
- `llm/fallback.py` — `FallbackLLMClient` (implements the same `LLMClient` protocol as one provider) + `build_default_chain(ProviderSettings)`, auto-wiring the chain from whatever is actually configured: primary first, then every other configured provider in a fixed order, then Ollama last. `AllProvidersExhaustedError` carries every attempt.
- `llm/pricing.py` extended: `PROVIDER_DEFAULT_RATES` + `resolve_rate` + `compute_cost_usd_or_zero` for every non-Anthropic provider. A verified default for Gemini (`$0.30`/`$2.50` per MTok, ai.google.dev); real `$0` for Ollama (local) and OpenRouter `:free` models; everywhere else (Azure, Groq, DeepSeek, non-free OpenRouter) is operator-configurable and honestly tracked as `cost_priced=False` when unset, rather than guessed. The original Anthropic-only `PRICING`/`compute_cost_usd` is unchanged.
- `schemas/handoffs.py`: added `LLMFailureKind.PROVIDER_UNAVAILABLE` for when every provider in the chain fails.
- `store/db.py` (SQLite schema for `runs`/`steps`/`llm_calls`/`approvals`, WAL mode) and `store/steps.py::LlmCallStore` (the `llm_calls` repository; `runs`/`steps`/`approvals` get their repositories in Phase 4/5).
- `llm/recording.py` — `RecordingClient` (persists every attempt, success or failure, to `llm_calls`) and `ReplayClient` (serves them back in order, re-validating each; `ReplayExhaustedError` if the replayed path asks for more than was recorded). `llm/fake.py` — `FakeClient` for scripted, network-free tests.
- 73 new tests (157 total, 1 skipped without live credentials): JSON extraction, provider settings, the fake client, the SQLite call store, recording/replay, the fallback chain's wiring logic (`build_default_chain` against many credential combinations), and every provider adapter against `httpx.MockTransport` (native-structured-output success, degrade-on-error fallback, unreachable-provider and malformed-response failure paths, Azure's key rotation). Plus one `@pytest.mark.live` smoke test against whatever provider is actually configured, skipped cleanly otherwise.
- `docs/adr/0006-record-replay-llm-io.md`, `docs/adr/0011-multi-provider-llm.md`, `docs/testing.md` (first full draft).

**Branding:**
- `assets/logo.png` — the project logo, and displayed at the top of `README.md`.

### Changed
- Project renamed **Casefile → ClaimGuard** across the codebase: the `casefile` package is now `claimguard` (`src/claimguard`), the `CASEFILE_*` env var prefix is now `CLAIMGUARD_*`, and every doc, Docker asset, and test reference was updated to match. The mock claims-system service (`claims-system` / `claims_system`) is unaffected — that name describes the insurer's system of record, not the project.
- LLM calls moved from Anthropic-only (originally planned) to multi-provider with automatic fallback, per operator preference — see ADR-0011. `docs/adr/0003-typed-handoffs.md` and `docs/implementation-plan.md` both carry forward-pointers to ADR-0011 rather than being rewritten, since the domain-layer decision in ADR-0003 didn't change, only the wire layer.

### Removed
- `respx` (dev dependency) — never actually used; every HTTP-calling client in this project accepts an injectable `transport`, so tests use `httpx.MockTransport`/`httpx.ASGITransport` directly instead.

<!-- This repo has a remote (origin -> github.com/rahulK098/claimguard); compare links are omitted here since docs/ itself is not committed. -->
