import pytest

from metis.planning.models import Goal, Step
from metis.providers.fake import FakeProvider
from metis.runtime.execution_controller import ExecutionController
from metis.runtime.loop import AgentLoop
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_execution_controller_marks_step_done(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    goal_id = state.create_goal(session_id, "Build Metis")
    plan_id = state.create_plan(goal_id)
    step_id = state.create_step(
        plan_id,
        order_index=1,
        title="Echo",
        action="Call echo",
        expected_output="echo result",
        verification_method="final response exists",
        done_condition="agent finishes without errors",
        allowed_tools=["echo"],
    )
    goal = state.get_goal(goal_id)
    step = state.get_step(step_id)

    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "echo", "arguments": {"value": "ok"}, "id": "c1"}]},
            {"content": '{"status":"done","summary":"done","evidence_refs":[],"artifact_refs":[],"next_action":""}'},
        ]
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"value": args["value"]}))
    loop = AgentLoop(provider=provider, registry=registry, state=state)
    controller = ExecutionController(loop=loop, state=state)

    result = await controller.run_step(session_id=session_id, goal=goal, step=step)

    assert result.verified is True
    assert state.get_step(step_id).status == "done"
