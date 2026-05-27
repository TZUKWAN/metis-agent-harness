"""Tests for AgentLoop session state memory leak fix."""

from __future__ import annotations

import time

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse, ProviderCapabilities
from metis.runtime.loop import AgentLoop
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProvider(BaseProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        return NormalizedResponse(content=resp.get("content", ""))

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type="test", model="test")


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda a, c: {"v": "ok"}))
    return registry


@pytest.mark.asyncio
async def test_session_state_cleaned_after_run():
    loop = AgentLoop(provider=FakeProvider([{"content": "done"}]), registry=_registry(), profile="small")
    from metis.runtime.response import AgentRunRequest
    await loop.run(AgentRunRequest(session_id="clean-test", messages=[{"role": "user", "content": "hi"}], max_turns=5))
    assert "clean-test" not in AgentLoop._SESSION_TOOL_COUNTS
    assert "clean-test" not in AgentLoop._SESSION_TOOL_FAILURES
    assert "clean-test" not in AgentLoop._SESSION_LAST_ACTIVITY


@pytest.mark.asyncio
async def test_session_state_cleaned_on_exception():
    class ExplodingProvider(BaseProvider):
        async def complete(self, messages, tools=None, **params):
            raise RuntimeError("boom")
        def capabilities(self):
            return ProviderCapabilities(provider_type="test", model="test")

    loop = AgentLoop(provider=ExplodingProvider(), registry=_registry(), profile="small")
    from metis.runtime.response import AgentRunRequest
    with pytest.raises(RuntimeError):
        await loop.run(AgentRunRequest(session_id="explode-test", messages=[{"role": "user", "content": "hi"}], max_turns=5))
    assert "explode-test" not in AgentLoop._SESSION_TOOL_COUNTS
    assert "explode-test" not in AgentLoop._SESSION_TOOL_FAILURES
    assert "explode-test" not in AgentLoop._SESSION_LAST_ACTIVITY


def test_prune_evicts_stale_sessions():
    AgentLoop._SESSION_LAST_ACTIVITY["stale-1"] = time.monotonic() - 7200
    AgentLoop._SESSION_TOOL_COUNTS["stale-1"] = {"echo": 1}
    AgentLoop._SESSION_TOOL_FAILURES["stale-1"] = {"echo": [time.monotonic() - 7200]}
    AgentLoop._prune_session_state()
    assert "stale-1" not in AgentLoop._SESSION_LAST_ACTIVITY
    assert "stale-1" not in AgentLoop._SESSION_TOOL_COUNTS
    assert "stale-1" not in AgentLoop._SESSION_TOOL_FAILURES


def test_prune_evicts_oldest_when_over_limit():
    original_limit = AgentLoop._MAX_TRACKED_SESSIONS
    AgentLoop._MAX_TRACKED_SESSIONS = 3
    try:
        now = time.monotonic()
        for i in range(5):
            sid = f"overflow-{i}"
            AgentLoop._SESSION_LAST_ACTIVITY[sid] = now - i
            AgentLoop._SESSION_TOOL_COUNTS[sid] = {}
            AgentLoop._SESSION_TOOL_FAILURES[sid] = {}
        AgentLoop._prune_session_state()
        assert len(AgentLoop._SESSION_LAST_ACTIVITY) <= 3
        assert "overflow-4" not in AgentLoop._SESSION_LAST_ACTIVITY
    finally:
        AgentLoop._MAX_TRACKED_SESSIONS = original_limit
        for i in range(5):
            AgentLoop._cleanup_session_state(f"overflow-{i}")


def test_cleanup_session_state_removes_all():
    AgentLoop._SESSION_LAST_ACTIVITY["full-1"] = time.monotonic()
    AgentLoop._SESSION_TOOL_COUNTS["full-1"] = {"echo": 2}
    AgentLoop._SESSION_TOOL_FAILURES["full-1"] = {"echo": [time.monotonic()]}
    AgentLoop._cleanup_session_state("full-1")
    assert "full-1" not in AgentLoop._SESSION_LAST_ACTIVITY
    assert "full-1" not in AgentLoop._SESSION_TOOL_COUNTS
    assert "full-1" not in AgentLoop._SESSION_TOOL_FAILURES
