"""FastAPI application factory for the orchestrator service."""

from fastapi import FastAPI

from casefile import __version__
from casefile.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="Casefile Orchestrator",
        version=__version__,
        description=(
            "Supervised multi-agent claims triage. Bounded by code-enforced ceilings, "
            "fully traced, replayable, and gated by a human before any payout action."
        ),
    )
    app.state.settings = settings

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "casefile-api", "version": __version__}

    return app
