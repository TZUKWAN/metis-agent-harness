"""Tests for global concurrency limiter on agent turns."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_default_concurrency_limit():
    from metis.app.web import create_app

    app = create_app()
    expected = max((os.cpu_count() or 2) * 2, 4)
    assert app.state.max_concurrent == expected
    assert app.state.concurrency_limiter._value == expected


@pytest.mark.asyncio
async def test_env_override_concurrency_limit(monkeypatch):
    monkeypatch.setenv("METIS_MAX_CONCURRENT", "2")
    from metis.app.web import create_app

    app = create_app()
    assert app.state.max_concurrent == 2
    assert app.state.concurrency_limiter._value == 2


@pytest.mark.asyncio
async def test_status_includes_concurrency():
    from metis.app.web import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "concurrency" in data
        assert data["concurrency"]["max"] == app.state.max_concurrent
        assert data["concurrency"]["active"] == 0
        assert data["concurrency"]["available"] == app.state.max_concurrent


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_requests(monkeypatch):
    monkeypatch.setenv("METIS_MAX_CONCURRENT", "1")
    from metis.app.web import create_app

    app = create_app()
    assert app.state.max_concurrent == 1

    gate = asyncio.Event()
    order: list[str] = []

    async def slow_run_agent_turn(*args, **kwargs):
        order.append("start")
        await gate.wait()
        order.append("end")
        from metis.runtime.response import AgentRunResult

        return AgentRunResult(final_text="ok", status="success", tool_results=[], trace_events=[])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("metis.app.web.run_agent_turn", side_effect=slow_run_agent_turn):
            task1 = asyncio.create_task(
                client.post("/api/v1/chat", json={"message": "hello", "session_id": "s1"})
            )
            task2 = asyncio.create_task(
                client.post("/api/v1/chat", json={"message": "world", "session_id": "s2"})
            )

            await asyncio.sleep(0.05)
            assert order == ["start"]
            gate.set()

            response1 = await task1
            response2 = await task2

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert order == ["start", "end", "start", "end"]
