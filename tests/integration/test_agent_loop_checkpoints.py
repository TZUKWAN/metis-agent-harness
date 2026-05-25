import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_records_start_and_final_checkpoints(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    loop = AgentLoop(
        provider=FakeProvider([{"content": "plain final", "finish_reason": "stop"}]),
        registry=ToolRegistry(),
        state=state,
        profile="deep",
    )

    result = await loop.run(
        AgentRunRequest(
            session_id="s1",
            messages=[{"role": "user", "content": "finish"}],
            max_turns=1,
            task_contract_hash="contract",
            prompt_stack_hash="prompt",
        )
    )

    checkpoints = state.list_checkpoints("s1")
    assert result.status == "final"
    assert [item["phase"] for item in checkpoints] == ["agent.start", "agent.finalization"]
    assert checkpoints[0]["task_contract_hash"] == "contract"
    assert checkpoints[0]["prompt_stack_hash"] == "prompt"
    assert state.latest_checkpoint("s1")["status"] == "final"
