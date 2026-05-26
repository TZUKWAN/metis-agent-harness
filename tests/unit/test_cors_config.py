"""Tests for CORS configuration and environment awareness."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_health_includes_environment():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "environment" in data
        assert data["environment"] == "development"


@pytest.mark.asyncio
async def test_cors_allows_configured_origin():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_cors_exposes_allowed_headers():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/chat",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == 200


def test_production_cors_warning_emitted(caplog):
    import os
    import logging

    original_env = os.environ.get("METIS_ENV")
    original_cors = os.environ.get("METIS_WEB_CORS_ORIGINS")
    os.environ["METIS_ENV"] = "production"
    os.environ.pop("METIS_WEB_CORS_ORIGINS", None)

    try:
        with caplog.at_level(logging.WARNING):
            from metis.app.web import create_app
            create_app()
        assert any("CORS" in r.message and "production" in r.message for r in caplog.records)
    finally:
        if original_env is not None:
            os.environ["METIS_ENV"] = original_env
        else:
            os.environ.pop("METIS_ENV", None)
        if original_cors is not None:
            os.environ["METIS_WEB_CORS_ORIGINS"] = original_cors
        else:
            os.environ.pop("METIS_WEB_CORS_ORIGINS", None)
