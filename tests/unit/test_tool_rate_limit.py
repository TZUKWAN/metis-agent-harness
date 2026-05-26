"""Tests for per-session tool call rate limiting."""

from __future__ import annotations

import pytest

from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, ToolCall
from metis.providers.base import BaseProvider, NormalizedResponse
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProvider(BaseProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        if "tool_calls" in resp:
            tcs = [ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"]) for tc in resp["tool_calls"]]
            return NormalizedResponse(tool_calls=tcs, content=resp.get("content", ""))
        return NormalizedResponse(content=resp.get("content", ""))


def _registry():
    registry = ToolRegistry()

    def handler(args, ctx):
        return {"value": args.get("value", "ok")}

    registry.register(ToolSpec(
        name="echo",
        description="Echo",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
        handler=handler,
        category="test",
        side_effect="read",
    ))
    return registry


@pytest.mark.asyncio
async def test_tool_rate_limit_blocks_after_threshold():
    # Create more tool calls than the limit
    tool_calls = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": f"v{i}"}, "id": f"c{i}"}]}
        for i in range(25)
    ]
    # Add a final response to end the loop
    tool_calls.append({"content": "done"})

    loop = AgentLoop(
        provider=FakeProvider(tool_calls),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-rate-limit",
        messages=[{"role": "user", "content": "test"}],
        max_turns=30,
    ))
    # Check that some tool results were rate limited
    rate_limited = [r for r in result.tool_results if r.metadata.get("rate_limited")]
    assert len(rate_limited) > 0


@pytest.mark.asyncio
async def test_tool_rate_limit_resets_per_session():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}, {"content": "done"}]),
        registry=_registry(),
        profile="small",
    )
    # First session
    await loop.run(AgentRunRequest(
        session_id="session-a",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    # Second session should start fresh
    result = await loop.run(AgentRunRequest(
        session_id="session-b",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    # No rate limiting in second session since it starts fresh
    rate_limited = [r for r in result.tool_results if r.metadata.get("rate_limited")]
    assert len(rate_limited) == 0


@pytest.mark.asyncio
async def test_different_tools_counted_separately():
    registry = ToolRegistry()

    def echo_handler(args, ctx):
        return {"value": args.get("value", "ok")}

    registry.register(ToolSpec(
        name="echo_a", description="Echo A",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
        handler=echo_handler, category="test", side_effect="read",
    ))
    registry.register(ToolSpec(
        name="echo_b", description="Echo B",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
        handler=echo_handler, category="test", side_effect="read",
    ))

    # Alternate between two tools many times
    responses = []
    for i in range(15):
        name = "echo_a" if i % 2 == 0 else "echo_b"
        responses.append({"tool_calls": [{"name": name, "arguments": {"value": f"v{i}"}, "id": f"c{i}"}]})
    responses.append({"content": "done"})

    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=registry,
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-separate-counts",
        messages=[{"role": "user", "content": "test"}],
        max_turns=20,
    ))
    # Each tool should be under the limit since they're alternated
    rate_limited = [r for r in result.tool_results if r.metadata.get("rate_limited")]
    assert len(rate_limited) == 0
