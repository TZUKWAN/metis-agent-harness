import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_records_contract_and_prompt_stack_hashes_in_trace():
    loop = AgentLoop(provider=FakeProvider([{"content": "done", "finish_reason": "stop"}]), registry=ToolRegistry())

    result = await loop.run(
        AgentRunRequest(
            messages=[{"role": "user", "content": "run"}],
            max_turns=1,
            task_contract_hash="contract-hash",
            prompt_stack_hash="prompt-hash",
        )
    )

    start_event = next(event for event in result.trace_events if event["event_type"] == "agent.start")
    assert start_event["attributes"]["task_contract_hash"] == "contract-hash"
    assert start_event["attributes"]["prompt_stack_hash"] == "prompt-hash"
