from metis.state.sqlite_store import SQLiteStateStore


def test_session_messages_and_tool_calls(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    session_id = store.create_session("s1", {"model": "fake"})

    msg_id = store.append_message(session_id, "user", "hello")
    call_id = store.record_tool_call(session_id, "echo", {"x": 1}, result='{"x":1}', status="ok")

    messages = store.list_messages(session_id)
    calls = store.list_tool_calls(session_id)

    assert msg_id == 1
    assert messages == [{"role": "user", "content": "hello", "metadata": {}}]
    assert calls[0]["id"] == call_id
    assert calls[0]["args"] == {"x": 1}


def test_list_sessions_returns_created_sessions(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    store.create_session("s1", {"model": "fake"})

    sessions = store.list_sessions()

    assert sessions[0]["id"] == "s1"
    assert sessions[0]["status"] == "active"
    assert sessions[0]["metadata"] == {"model": "fake"}


def test_session_updated_at_changes_when_messages_are_appended(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    store.create_session("s1")
    before = store.list_sessions()[0]["updated_at"]

    store.append_message("s1", "user", "hello")

    after = store.list_sessions()[0]["updated_at"]
    assert after >= before


def test_goal_plan_step_lifecycle(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    session_id = store.create_session("s1")
    goal_id = store.create_goal(
        session_id,
        "Build harness",
        acceptance_criteria=["tests pass"],
        constraints=["no fake completion"],
    )
    plan_id = store.create_plan(goal_id)
    step_id = store.create_step(
        plan_id,
        order_index=1,
        title="Implement hooks",
        action="Create HookBus",
        required_inputs=["task list"],
        expected_output="HookBus module",
        allowed_tools=["write_file"],
        verification_method="pytest",
        done_condition="hook tests pass",
    )

    goal = store.get_goal(goal_id)
    plan = store.get_plan(plan_id)
    step = store.get_step(step_id)
    steps = store.list_steps(plan_id)

    assert goal is not None
    assert goal.objective == "Build harness"
    assert goal.acceptance_criteria == ["tests pass"]
    assert plan is not None
    assert plan.goal_id == goal_id
    assert step is not None
    assert step.status == "pending"
    assert step.allowed_tools == ["write_file"]
    assert steps[0].id == step_id

    store.update_step_status(step_id, "done")
    store.update_goal_status(goal_id, "complete")

    assert store.get_step(step_id).status == "done"
    assert store.get_goal(goal_id).status == "complete"


def test_run_checkpoints_lifecycle(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    session_id = store.create_session("s1")

    first = store.record_checkpoint(
        session_id,
        phase="agent.start",
        status="started",
        task_contract_hash="contract",
        prompt_stack_hash="prompt",
        metadata={"turn": 0},
    )
    second = store.record_checkpoint(session_id, phase="agent.finalization", status="final")

    checkpoints = store.list_checkpoints(session_id)
    latest = store.latest_checkpoint(session_id)

    assert checkpoints[0]["id"] == first
    assert checkpoints[0]["task_contract_hash"] == "contract"
    assert checkpoints[0]["prompt_stack_hash"] == "prompt"
    assert checkpoints[0]["metadata"] == {"turn": 0}
    assert latest["id"] == second
    assert latest["phase"] == "agent.finalization"
