"""Tests for tool call deduplication via result cache."""

from __future__ import annotations

import pytest

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
async def test_dedup_caches_read_file_result():
    registry = ToolRegistry()
    call_count = {"n": 0}

    def echo_handler(args, ctx):
        call_count["n"] += 1
        return {"value": args["value"], "call": call_count["n"]}

    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}, echo_handler))

    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c2"}]},
        {"content": "done"},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small")
    result = await loop.run(AgentRunRequest(
        session_id="test-dedup",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    assert call_count["n"] == 1
    cached_meta = result.tool_results[1].metadata
    assert cached_meta.get("from_cache") is True


@pytest.mark.asyncio
async def test_dedup_different_args_not_cached():
    registry = ToolRegistry()
    call_count = {"n": 0}

    def echo_handler(args, ctx):
        call_count["n"] += 1
        return {"value": args["value"]}

    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}, echo_handler))

    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "a"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "b"}, "id": "c2"}]},
        {"content": "done"},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small")
    result = await loop.run(AgentRunRequest(
        session_id="test-no-dedup",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    assert call_count["n"] == 2
