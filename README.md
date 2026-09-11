# ClaimGuard

> A bounded, observable, replayable multi-agent claims triage system — that never pays out without a human.

**Status:** Phase 0 (bootstrap) — see [docs/implementation-plan.md](docs/implementation-plan.md).

ClaimGuard is a supervised multi-agent graph that triages synthetic auto-insurance claims. The interesting part is not the agents; it is the control plane around them:

- **Bounded** — a per-claim budget ceiling, step ceiling and loop guard are enforced in code, not in a prompt.
- **Observable** — every node transition, LLM call and tool call is a span in Jaeger and a row in a step log.
- **Replayable** — every LLM request/response is recorded; any run can be replayed deterministically to the same terminal state.
- **Never autonomous over money** — a payout recommendation parks the run until a human approves it over HTTP, and the (mocked) claims system rejects any write that does not carry a valid approval token.

## Quick start

```bash
cp env.example .env             # add ANTHROPIC_API_KEY
docker compose up --build
curl http://localhost:8000/healthz
curl http://localhost:8001/healthz
open http://localhost:16686      # Jaeger UI
```

## Documentation

Everything lives under [docs/](docs/README.md): architecture, tech stack, data model, guarantees, ADRs, API reference, runbook and testing guide.

## License

MIT — see [LICENSE](LICENSE).
