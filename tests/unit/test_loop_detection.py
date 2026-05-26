"""Tests for response loop detection in AgentLoop."""

from __future__ import annotations

import pytest

from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, ToolCall, NormalizedResponse
from metis.providers.base import BaseProvider
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
async def test_loop_detection_triggers_on_repeated_tool_calls():
    # Same tool call pattern 4 times, then done
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": f"c{i}"}]}
        for i in range(4)
    ]
    responses.append({"content": "done"})

    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-loop",
        messages=[{"role": "user", "content": "test"}],
        max_turns=10,
    ))
    assert result.status == "blocked"
    assert any("loop detected" in e.lower() for e in result.errors)


def test_detect_response_loop_on_text_signatures():
    """Loop detection works on text signatures even though real runs rarely hit this path
    (text responses typically trigger finalization and end the run before loop builds)."""
    sigs = ["text:hello", "text:hello", "text:hello"]
    assert AgentLoop._detect_response_loop(sigs) is True


@pytest.mark.asyncio
async def test_loop_detection_does_not_trigger_on_two_repeats():
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c2"}]},
        {"content": "done"},
    ]

    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-no-loop",
        messages=[{"role": "user", "content": "test"}],
        max_turns=10,
    ))
    assert result.status != "blocked"


@pytest.mark.asyncio
async def test_loop_detection_does_not_trigger_on_varied_responses():
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "a"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "b"}, "id": "c2"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "c"}, "id": "c3"}]},
        {"content": "done"},
    ]

    loop = AgentLoop(
        provider=FakeProvider(responses),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-varied",
        messages=[{"role": "user", "content": "test"}],
        max_turns=10,
    ))
    assert result.status != "blocked"


def test_turn_signature_tools():
    resp = NormalizedResponse(
        tool_calls=[ToolCall(id="1", name="echo", arguments={"value": "test"})],
        content="",
    )
    sig1 = AgentLoop._turn_signature(resp)
    sig2 = AgentLoop._turn_signature(resp)
    assert sig1 == sig2
    assert "tools:echo" in sig1


def test_turn_signature_text():
    resp = NormalizedResponse(content="hello world")
    sig = AgentLoop._turn_signature(resp)
    assert sig == "text:hello world"


def test_detect_response_loop_true():
    assert AgentLoop._detect_response_loop(["a", "a", "a"]) is True
    assert AgentLoop._detect_response_loop(["a", "b", "a", "a", "a"]) is True


def test_detect_response_loop_false():
    assert AgentLoop._detect_response_loop(["a", "a"]) is False
    assert AgentLoop._detect_response_loop(["a", "b", "c"]) is False
    assert AgentLoop._detect_response_loop([]) is False
