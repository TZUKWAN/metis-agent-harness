import pytest

from metis.providers.fake import FakeProvider
from metis.providers.parsers.repair import ParserChain
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_agent_loop_repairs_unparseable_tool_call():
    provider = FakeProvider(
        [
            {
                "content": '<tool_call>{"name":"echo","arguments": }</tool_call>',
                "raw": '<tool_call>{"name":"echo","arguments": }</tool_call>',
            },
            {
                "content": "```json\n{\"tool\":\"echo\",\"arguments\":{\"value\":\"ok\"}}\n```",
                "raw": "```json\n{\"tool\":\"echo\",\"arguments\":{\"value\":\"ok\"}}\n```",
            },
            {"content": '{"status":"done","summary":"ok","evidence_refs":[],"artifact_refs":[],"next_action":""}'},
        ]
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"value": args["value"]}))
    loop = AgentLoop(provider=provider, registry=registry, tool_call_parser=ParserChain())

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "run"}], max_turns=2))

    assert result.status == "final"
    assert result.tool_results[0].tool_name == "echo"
    assert any("ParserError" in error for error in result.errors)
    event_types = [event["event_type"] for event in result.trace_events]
    assert "parser.repair.request" in event_types
    assert "parser.repair.result" in event_types
    repair_result = next(event for event in result.trace_events if event["event_type"] == "parser.repair.result")
    assert repair_result["status"] == "ok"
    assert repair_result["attributes"]["tool_call_count"] == 1
