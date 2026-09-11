"""FastAPI application for the mock claims system of record."""

from fastapi import FastAPI

from claims_system import __version__

app = FastAPI(
    title="Claims System (mock)",
    version=__version__,
    description=(
        "Mocked system of record. Read endpoints serve policy, prior-claim and repair "
        "benchmark data. The decision endpoint rejects any write without a valid "
        "human-minted approval token."
    ),
)


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "claims-system", "version": __version__}
