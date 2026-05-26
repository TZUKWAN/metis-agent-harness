"""Tests for FastAPI request timeout middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_fast_request_succeeds():
    from metis.app.web import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert "healthy" in response.text.lower()
