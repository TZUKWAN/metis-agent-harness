import json

import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_single_tool_then_final():
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "echo", "arguments": {"value": "ok"}, "id": "c1"}]},
            {
                "content": '{"status":"done","summary":"final answer","evidence_refs":[],"artifact_refs":[],"next_action":""}',
                "usage": {"total_tokens": 10},
            },
        ]
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"echo": args["value"]}))
    loop = AgentLoop(provider=provider, registry=registry)

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "run"}], max_turns=3))

    assert result.status == "final"
    assert "final answer" in result.final_text
    assert json.loads(result.tool_results[0].content) == {"echo": "ok"}
    assert result.turns_used == 2
    event_types = [event["event_type"] for event in result.trace_events]
    assert "agent.start" in event_types
    assert "model.request" in event_types
    assert "model.response" in event_types
    assert "tool.request" in event_types
    assert "tool.result" in event_types
    assert "finalization.check" in event_types
    assert "finalization.result" in event_types
    tool_result_event = next(event for event in result.trace_events if event["event_type"] == "tool.result")
    assert tool_result_event["tool_name"] == "echo"
    assert tool_result_event["attributes"]["gen_ai.operation.name"] == "execute_tool"


@pytest.mark.asyncio
async def test_max_turns():
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "echo", "arguments": {"value": "1"}, "id": "c1"}]},
            {"tool_calls": [{"name": "echo", "arguments": {"value": "2"}, "id": "c2"}]},
        ]
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: args))
    loop = AgentLoop(provider=provider, registry=registry)

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "run"}], max_turns=2))

    assert result.status == "max_turns"
    assert result.turns_used == 2
