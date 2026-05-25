import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_blocks_when_strict_final_output_repair_fails():
    provider = FakeProvider([{"content": "done"}, {"content": "still not json"}])
    loop = AgentLoop(provider=provider, registry=ToolRegistry(), profile="small")

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "finish"}], max_turns=1))

    assert result.status == "blocked"
    assert any("StrictOutput" in error for error in result.errors)
    event_types = [event["event_type"] for event in result.trace_events]
    assert "finalization.repair.request" in event_types
    assert "finalization.repair.result" in event_types
    repair_result = next(event for event in result.trace_events if event["event_type"] == "finalization.repair.result")
    assert repair_result["status"] == "failed"
