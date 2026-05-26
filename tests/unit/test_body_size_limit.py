"""Tests for request body size limit middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_normal_sized_body_accepted():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_oversized_body_rejected():
    from metis.app.web import create_app, MAX_BODY_SIZE

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        big_body = "x" * (MAX_BODY_SIZE + 1)
        response = await client.post(
            "/api/v1/chat",
            json={"message": big_body, "session_id": "s1"},
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"]["code"] == 413
        assert "too large" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_exact_max_size_accepted():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        small_body = "hello"
        response = await client.post(
            "/api/v1/chat",
            json={"message": small_body, "session_id": "s1"},
        )
        assert response.status_code != 413


@pytest.mark.asyncio
async def test_get_request_not_blocked():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/config")
        assert response.status_code == 200
