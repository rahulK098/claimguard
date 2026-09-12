"""Regenerates docs/api/openapi-*.json from the live FastAPI apps.

Run this after any change to routes in either service:

    uv run python scripts/export_openapi.py

Both apps are constructed with default settings purely to read their route
table and produce a schema -- no lifespan is run, so this never touches the
database or fixture files, just the route/schema definitions.
"""

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "api"


def _write(name: str, schema: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    from claimguard.api.app import create_app as create_orchestrator_app
    from claims_system.app import create_app as create_claims_system_app

    _write("openapi-claimguard.json", create_orchestrator_app().openapi())
    _write("openapi-claims-system.json", create_claims_system_app().openapi())


if __name__ == "__main__":
    main()
