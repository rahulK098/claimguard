"""Fixtures for tests that need a live (in-process) claims-system app."""

from collections.abc import AsyncIterator

import httpx
import pytest

from claimguard.tools.claims_system import ClaimsSystemClient
from claims_system.app import create_app
from claims_system.config import Settings as ClaimsSystemSettings


@pytest.fixture
async def claims_system_client(
    claims_system_settings: ClaimsSystemSettings,
) -> AsyncIterator[ClaimsSystemClient]:
    """A ClaimsSystemClient wired to an in-process app via ASGI transport.

    Runs the app's lifespan (data + store setup) manually since ASGITransport
    doesn't trigger it the way a real server startup would.
    """
    app = create_app(claims_system_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        client = ClaimsSystemClient(base_url="http://testserver", transport=transport)
        try:
            yield client
        finally:
            await client.aclose()
