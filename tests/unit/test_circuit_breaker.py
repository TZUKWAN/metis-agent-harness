"""Tests for tool call circuit breaker."""

from __future__ import annotations

import json
import time

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

    def fail_handler(args, ctx):
        raise RuntimeError("always fails")

    def ok_handler(args, ctx):
        return {"value": args.get("value", "ok")}

    registry.register(ToolSpec(
        name="fail_tool",
        description="Always fails",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
        handler=fail_handler,
        category="test",
        side_effect="read",
    ))
    registry.register(ToolSpec(
        name="ok_tool",
        description="Always ok",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
        handler=ok_handler,
        category="test",
        side_effect="read",
    ))
    return registry


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_after_threshold():
    # 4 tool calls with different args to avoid loop detection, then done
    responses = [
        {"tool_calls": [{"name": "fail_tool", "arguments": {"value": f"v{i}"}, "id": f"c{i}"}]}
        for i in range(4)
    ]
    responses.append({"content": "done"})

    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-cb",
        messages=[{"role": "user", "content": "test"}],
        max_turns=10,
    ))
    # At least one call should be circuit-broken after 3 failures
    cb_results = [r for r in result.tool_results if r.metadata.get("circuit_breaker")]
    assert len(cb_results) >= 1


@pytest.mark.asyncio
async def test_circuit_breaker_resets_per_session():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}]),
        registry=_registry(),
        profile="small",
    )
    # Manually record failures for session-a
    AgentLoop._record_tool_failure("session-a", "fail_tool")
    AgentLoop._record_tool_failure("session-a", "fail_tool")
    AgentLoop._record_tool_failure("session-a", "fail_tool")

    # session-b should not be affected
    cb = AgentLoop._check_circuit_breaker("session-b", "fail_tool")
    assert cb is None


@pytest.mark.asyncio
async def test_circuit_breaker_allows_success():
    responses = [
        {"tool_calls": [{"name": "ok_tool", "arguments": {"value": "v1"}, "id": "c1"}]},
        {"content": "done"},
    ]
    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-cb-ok",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    cb_results = [r for r in result.tool_results if r.metadata.get("circuit_breaker")]
    assert len(cb_results) == 0


def test_check_circuit_breaker_returns_none_under_threshold():
    AgentLoop._SESSION_TOOL_FAILURES.clear()
    assert AgentLoop._check_circuit_breaker("s1", "t1") is None
    AgentLoop._record_tool_failure("s1", "t1")
    AgentLoop._record_tool_failure("s1", "t1")
    assert AgentLoop._check_circuit_breaker("s1", "t1") is None


def test_check_circuit_breaker_returns_message_over_threshold():
    AgentLoop._SESSION_TOOL_FAILURES.clear()
    now = time.monotonic()
    # Inject 3 recent failures
    AgentLoop._SESSION_TOOL_FAILURES["s2"] = {"t2": [now, now, now]}
    msg = AgentLoop._check_circuit_breaker("s2", "t2")
    assert msg is not None
    assert "temporarily unavailable" in msg


def test_record_tool_failure_prunes_stale_entries():
    AgentLoop._SESSION_TOOL_FAILURES.clear()
    now = time.monotonic()
    old = now - AgentLoop._CIRCUIT_BREAKER_WINDOW - 1
    AgentLoop._SESSION_TOOL_FAILURES["s3"] = {"t3": [old, now]}
    AgentLoop._record_tool_failure("s3", "t3")
    failures = AgentLoop._SESSION_TOOL_FAILURES["s3"]["t3"]
    assert old not in failures
    assert len(failures) == 2  # old pruned, now kept, new now appended


def test_circuit_breaker_cooldown_allows_recovery():
    AgentLoop._SESSION_TOOL_FAILURES.clear()
    now = time.monotonic()
    # Failures just at the boundary of cooldown
    AgentLoop._SESSION_TOOL_FAILURES["s4"] = {"t4": [now - AgentLoop._CIRCUIT_BREAKER_COOLDOWN - 1] * 3}
    msg = AgentLoop._check_circuit_breaker("s4", "t4")
    assert msg is None
