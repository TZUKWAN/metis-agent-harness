"""Tests for Pydantic input validation on chat endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


@pytest.mark.asyncio
async def test_chat_missing_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"session_id": "s1"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_empty_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"message": "", "session_id": "s1"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_whitespace_only_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"message": "   ", "session_id": "s1"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_oversized_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        big_message = "x" * 50001
        response = await client.post("/api/v1/chat", json={"message": big_message, "session_id": "s1"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_sse_missing_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat/sse", json={"session_id": "s1"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_legacy_chat_missing_message_returns_422():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={"session_id": "s1"})
        assert response.status_code == 422


def test_chat_request_model_valid():
    from metis.app.schemas import ChatRequest

    req = ChatRequest(message="hello", session_id="s1")
    assert req.message == "hello"
    assert req.session_id == "s1"


def test_chat_request_model_default_session():
    from metis.app.schemas import ChatRequest

    req = ChatRequest(message="hello")
    assert req.session_id == ""


def test_chat_request_model_rejects_no_message():
    from metis.app.schemas import ChatRequest
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ChatRequest(session_id="s1")


def test_chat_request_model_rejects_oversized():
    from metis.app.schemas import ChatRequest
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ChatRequest(message="x" * 50001)
