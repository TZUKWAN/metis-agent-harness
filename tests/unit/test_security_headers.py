"""Tests for security response headers middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_nosniff_header_present():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_frame_options_header_present():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.asyncio
async def test_referrer_policy_header_present():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_api_endpoints_have_no_store_cache():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/config")
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_non_api_endpoints_no_cache_header():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert "Cache-Control" not in response.headers or response.headers.get("Cache-Control") != "no-store"
