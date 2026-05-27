"""Tests for token usage tracking events."""

from __future__ import annotations

import json

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
    def __init__(self, content="", tool_calls=None, usage=None, **kwargs):
        self.content = content
        self.tool_calls = []
        if tool_calls:
            for tc in tool_calls:
                self.tool_calls.append(ToolCall(id=tc.get("id", "c"), name=tc["name"], arguments=tc["arguments"]))
        self.finish_reason = "stop"
        self.usage = usage or {}
        self.raw = content


@pytest.mark.asyncio
async def test_token_usage_event_emitted_per_turn():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]}, lambda a, c: {"v": a["v"]}))

    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"v": "x"}, "id": "c1"}], "usage": {"prompt_tokens": 100, "completion_tokens": 50}},
        {"content": "done", "usage": {"prompt_tokens": 80, "completion_tokens": 30}},
    ]
    hooks = HookBus()
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    events = []
    hooks.register("model.token_usage", lambda data: events.append(data))

    await loop.run(AgentRunRequest(session_id="tok-test", messages=[{"role": "user", "content": "go"}], max_turns=5))

    assert len(events) == 2
    assert events[0]["turn"] == 1
    assert events[0]["turn_usage"]["prompt_tokens"] == 100
    assert events[0]["cumulative_usage"]["prompt_tokens"] == 100
    assert events[1]["turn"] == 2
    assert events[1]["cumulative_usage"]["prompt_tokens"] == 180


@pytest.mark.asyncio
async def test_no_event_when_usage_empty():
    registry = ToolRegistry()

    responses = [
        {"content": "done", "usage": {}},
    ]
    hooks = HookBus()
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", hooks=hooks)
    events = []
    hooks.register("model.token_usage", lambda data: events.append(data))

    await loop.run(AgentRunRequest(session_id="no-usage", messages=[{"role": "user", "content": "go"}], max_turns=5))

    assert len(events) == 0
