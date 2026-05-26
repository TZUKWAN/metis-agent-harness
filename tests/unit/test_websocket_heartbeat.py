"""Tests for WebSocket heartbeat in chat_stream."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_heartbeat_sends_ping_during_long_turn():
    from metis.app.web import create_app
    from metis.runtime.response import AgentRunResult

    app = create_app()

    turn_started = asyncio.Event()
    turn_release = asyncio.Event()

    async def slow_turn(*args, **kwargs):
        turn_started.set()
        await turn_release.wait()
        return AgentRunResult(final_text="done", status="success", tool_results=[], trace_events=[])

    from starlette.testclient import TestClient

    with patch("metis.app.web.run_agent_turn", side_effect=slow_turn):
        client = TestClient(app)
        with client.websocket_connect("/api/v1/chat/stream") as ws:
            ws.send_json({"message": "hello", "session_id": "s1"})

            messages = []
            for _ in range(10):
                raw = ws.receive_json()
                messages.append(raw)
                if raw.get("type") == "ping":
                    turn_release.set()
                    break
                if raw.get("type") == "done":
                    break

            ping_found = any(m.get("type") == "ping" for m in messages)
            assert ping_found, f"Expected ping message, got: {[m.get('type') for m in messages]}"


@pytest.mark.asyncio
async def test_no_heartbeat_after_turn_completes():
    from metis.app.web import create_app
    from metis.runtime.response import AgentRunResult

    app = create_app()

    async def fast_turn(*args, **kwargs):
        return AgentRunResult(final_text="quick", status="success", tool_results=[], trace_events=[])

    from starlette.testclient import TestClient

    with patch("metis.app.web.run_agent_turn", side_effect=fast_turn):
        client = TestClient(app)
        with client.websocket_connect("/api/v1/chat/stream") as ws:
            ws.send_json({"message": "hello", "session_id": "s1"})

            messages = []
            for _ in range(5):
                raw = ws.receive_json()
                messages.append(raw)
                if raw.get("type") == "done":
                    break

            types = [m.get("type") for m in messages]
            assert "ping" not in types, f"Heartbeat should not fire for fast turns, got: {types}"
            assert "done" in types
