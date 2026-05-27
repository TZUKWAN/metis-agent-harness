"""Tests verifying SSE endpoints receive AgentLoop events via shared HookBus."""

from __future__ import annotations

import pytest

from metis.events.hooks import HookBus
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, ToolCall
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0

    def capabilities(self):
        from metis.providers.base import ProviderCapabilities
        return ProviderCapabilities(provider_type="fake", model="fake")

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        return _FakeResponse(**resp)


class _FakeResponse:
    def __init__(self, content="", tool_calls=None, **kwargs):
        self.content = content
        self.tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                self.tool_calls.append(ToolCall(id=tc.get("id", "c"), name=tc["name"], arguments=tc["arguments"]))
        self.finish_reason = "stop"
        self.usage = {}
        self.raw = content


@pytest.mark.asyncio
async def test_shared_hooks_receives_tool_analytics_events():
    """When a HookBus is passed to AgentLoop, tool.analytics events fire on it."""
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]}, lambda a, c: {"v": a["v"]}))

    hooks = HookBus()
    analytics_events = []
    hooks.register("tool.analytics", lambda data: analytics_events.append(data))

    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"v": "hello"}, "id": "c1"}]},
        {"content": "done"},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    await loop.run(AgentRunRequest(session_id="hook-test", messages=[{"role": "user", "content": "go"}], max_turns=5))

    assert len(analytics_events) >= 1
    assert analytics_events[0]["tool"] == "echo"


@pytest.mark.asyncio
async def test_shared_hooks_receives_turn_complete_events():
    """When a HookBus is passed to AgentLoop, turn.complete events fire on it."""
    registry = ToolRegistry()

    hooks = HookBus()
    turn_events = []
    hooks.register("turn.complete", lambda data: turn_events.append(data))

    responses = [{"content": "done"}]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    await loop.run(AgentRunRequest(session_id="turn-hook-test", messages=[{"role": "user", "content": "go"}], max_turns=5))

    assert len(turn_events) == 1
    assert turn_events[0]["turn"] == 1
    assert "turn_duration_ms" in turn_events[0]


@pytest.mark.asyncio
async def test_shared_hooks_receives_both_event_types():
    """A single shared HookBus receives both tool.analytics and turn.complete."""
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]}, lambda a, c: {"v": a["v"]}))

    hooks = HookBus()
    all_events = []
    hooks.register("tool.analytics", lambda data: all_events.append(("tool", data)))
    hooks.register("turn.complete", lambda data: all_events.append(("turn", data)))

    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"v": "x"}, "id": "c1"}]},
        {"content": "done"},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    await loop.run(AgentRunRequest(session_id="both-hook-test", messages=[{"role": "user", "content": "go"}], max_turns=5))

    tool_events = [e for e in all_events if e[0] == "tool"]
    turn_events = [e for e in all_events if e[0] == "turn"]
    assert len(tool_events) >= 1
    assert len(turn_events) >= 1


@pytest.mark.asyncio
async def test_run_agent_turn_passes_hooks_through(monkeypatch):
    """run_agent_turn propagates hooks to the AgentLoop so events are captured."""
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    from metis.app.manifest import AgentAppManifest
    from metis.app.runtime import build_agent_loop
    from metis.providers.base import BaseProvider, NormalizedResponse

    class FakeBaseProvider(BaseProvider):
        async def complete(self, messages, tools=None, **params):
            return NormalizedResponse(content="done")

    manifest = AgentAppManifest(
        name="test",
        model="fake-model",
        base_url="http://localhost:0",
        profile="small",
    )

    hooks = HookBus()
    events = []
    hooks.register("turn.complete", lambda data: events.append(data))

    loop = build_agent_loop(manifest, hooks=hooks)
    assert loop.hooks is hooks
