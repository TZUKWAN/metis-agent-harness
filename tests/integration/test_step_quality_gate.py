import pytest

from metis.artifacts.store import ArtifactStore
from metis.planning.models import Goal
from metis.providers.fake import FakeProvider
from metis.runtime.execution_controller import ExecutionController
from metis.runtime.loop import AgentLoop
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_step_quality_gate_blocks_done_without_artifact(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    goal_id = state.create_goal(session_id, "Create report")
    plan_id = state.create_plan(goal_id)
    step_id = state.create_step(
        plan_id,
        order_index=1,
        title="Report",
        action="Create report",
        expected_output="report",
        verification_method="quality gate",
        done_condition="artifact exists",
        required_gates=["artifact_exists"],
    )
    step = state.get_step(step_id)
    provider = FakeProvider(
        [{"content": '{"status":"done","summary":"done","evidence_refs":[],"artifact_refs":[],"next_action":""}'}]
    )
    loop = AgentLoop(provider=provider, registry=ToolRegistry(), state=state)
    controller = ExecutionController(loop=loop, state=state, artifact_store=ArtifactStore(state))

    result = await controller.run_step(session_id=session_id, goal=state.get_goal(goal_id), step=step)

    assert result.verified is False
    assert state.get_step(step_id).status == "failed"
    assert "No artifacts" in result.reason
