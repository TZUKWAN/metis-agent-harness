"""Tests for per-turn timing metrics."""

from __future__ import annotations

import pytest

from metis.events.hooks import HookBus
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, ToolCall
from metis.tools.registry import ToolRegistry


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0

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
async def test_turn_complete_event_emitted():
    registry = ToolRegistry()
    responses = [{"content": "done"}]
    hooks = HookBus()
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    events = []
    hooks.register("turn.complete", lambda data: events.append(data))

    await loop.run(AgentRunRequest(session_id="timing-test", messages=[{"role": "user", "content": "go"}], max_turns=5))

    assert len(events) == 1
    assert events[0]["turn"] == 1
    assert "turn_duration_ms" in events[0]
    assert events[0]["turn_duration_ms"] >= 0


@pytest.mark.asyncio
async def test_turn_timing_in_trace_events():
    registry = ToolRegistry()
    responses = [{"content": "done"}]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small")

    result = await loop.run(AgentRunRequest(session_id="trace-timing", messages=[{"role": "user", "content": "go"}], max_turns=5))

    timing_events = [e for e in result.trace_events if e.get("event_type") == "turn.timing"]
    assert len(timing_events) == 1
    assert "turn_duration_ms" in timing_events[0]["attributes"]
