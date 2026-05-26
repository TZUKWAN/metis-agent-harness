"""Tests for global exception handler."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_http_exception_returns_structured_error():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == 404
        assert "session" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_unhandled_exception_returns_safe_response():
    from metis.app.web import create_app

    app = create_app()

    @app.get("/_test_crash")
    async def _test_crash():
        raise ValueError("secret stack trace info")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test_crash")
        assert response.status_code == 500
        data = response.json()
        assert data["error"]["code"] == 500
        assert data["error"]["message"] == "Internal server error"
        assert "secret" not in response.text
        assert "ValueError" not in response.text


@pytest.mark.asyncio
async def test_unhandled_exception_logged(caplog):
    import logging

    from metis.app.web import create_app

    app = create_app()

    @app.get("/_test_crash_log")
    async def _test_crash_log():
        raise RuntimeError("boom")

    transport = ASGITransport(app=app)
    with caplog.at_level(logging.ERROR):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/_test_crash_log")
            assert response.status_code == 500

    assert "boom" in caplog.text or "Unhandled exception" in caplog.text
