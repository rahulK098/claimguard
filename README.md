<p align="center">
  <img src="assets/logo.png" alt="ClaimGuard logo" width="260">
</p>

<h1 align="center">ClaimGuard</h1>
<p align="center"><em>Safe Agents. Trusted Claims.</em></p>
<p align="center">Bounded · Observable · Replayable · Human-Approved</p>

> A bounded, observable, replayable multi-agent claims triage system — that never pays out without a human.

**Status:** Phase 3 of 8 (LLM client layer) — see `docs/implementation-plan.md` (local working tree; not committed, see Documentation below).

ClaimGuard is a supervised multi-agent graph that triages synthetic auto-insurance claims. The interesting part is not the agents; it is the control plane around them:

- **Bounded** — a per-claim budget ceiling, step ceiling and loop guard are enforced in code, not in a prompt.
- **Observable** — every node transition, LLM call and tool call is a span in Jaeger and a row in a step log.
- **Replayable** — every LLM request/response is recorded; any run can be replayed deterministically to the same terminal state.
- **Never autonomous over money** — a payout recommendation parks the run until a human approves it over HTTP, and the (mocked) claims system rejects any write that does not carry a valid approval token.

## Quick start

```bash
cp env.example .env             # fill in at least one LLM provider's credentials
docker compose up --build
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
open http://localhost:16686      # Jaeger UI
```

ClaimGuard talks to whichever LLM provider is configured — Azure OpenAI, Anthropic, OpenRouter, Groq, Gemini, DeepSeek, or local Ollama — with automatic fallback across every provider that has credentials set. See `env.example` for the full list.

## Documentation

Architecture, tech stack, data model, guarantees, ADRs, API reference, runbook and testing guide are maintained under `docs/` in this repo's working tree. That directory is intentionally not committed to git (see `.gitignore`), so it won't render on GitHub — clone the repo to read it locally, starting from `docs/README.md`.

## License

MIT — see [LICENSE](LICENSE).
