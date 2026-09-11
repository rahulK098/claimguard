# syntax=docker/dockerfile:1.7
#
# Single image for both services. docker-compose selects the entrypoint:
#   api            -> uvicorn claimguard.api.app:create_app --factory
#   claims-system  -> uvicorn claims_system.app:app
#
# Build is two-stage so the runtime image has no uv, no build tools and no
# test dependencies.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Resolve dependencies first so this layer caches across source edits.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app \
    && mkdir -p /data && chown app:app /data

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --chown=app:app data ./data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
VOLUME ["/data"]

# Default to the orchestrator; compose overrides for claims-system.
EXPOSE 8000
CMD ["uvicorn", "claimguard.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
