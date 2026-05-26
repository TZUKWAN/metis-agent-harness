"""Tests for metis/state/sqlite_store.py."""

import json

import pytest

from metis.state.sqlite_store import SQLiteStateStore


@pytest.fixture
def store(tmp_path):
    return SQLiteStateStore(tmp_path / "test.db")


class TestSessionCRUD:
    def test_create_session(self, store):
        sid = store.create_session()
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["id"] == sid

    def test_create_session_with_id(self, store):
        sid = store.create_session(session_id="abc123")
        assert sid == "abc123"

    def test_create_session_with_metadata(self, store):
        sid = store.create_session(metadata={"key": "val"})
        sessions = store.list_sessions()
        assert sessions[0]["metadata"] == {"key": "val"}

    def test_create_session_idempotent(self, store):
        store.create_session(session_id="x")
        store.create_session(session_id="x")
        assert len(store.list_sessions()) == 1


class TestMessages:
    def test_append_and_list(self, store):
        sid = store.create_session()
        store.append_message(sid, "user", "hello")
        store.append_message(sid, "assistant", "hi there")
        msgs = store.list_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "hi there"

    def test_empty_messages(self, store):
        sid = store.create_session()
        assert store.list_messages(sid) == []


class TestToolCalls:
    def test_record_and_list(self, store):
        sid = store.create_session()
        store.record_tool_call(sid, "read_file", {"path": "a.txt"}, result="contents", status="ok")
        calls = store.list_tool_calls(sid)
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "read_file"
        assert calls[0]["args"] == {"path": "a.txt"}

    def test_tool_call_with_error(self, store):
        sid = store.create_session()
        store.record_tool_call(sid, "bad_tool", {}, status="error", error="boom")
        calls = store.list_tool_calls(sid)
        assert calls[0]["error"] == "boom"


class TestGoalsAndPlans:
    def test_create_goal(self, store):
        sid = store.create_session()
        gid = store.create_goal(sid, "build feature X", acceptance_criteria=["works"])
        goal = store.get_goal(gid)
        assert goal is not None
        assert goal.objective == "build feature X"
        assert goal.acceptance_criteria == ["works"]

    def test_update_goal_status(self, store):
        sid = store.create_session()
        gid = store.create_goal(sid, "objective")
        store.update_goal_status(gid, "completed")
        assert store.get_goal(gid).status == "completed"

    def test_create_plan(self, store):
        sid = store.create_session()
        gid = store.create_goal(sid, "obj")
        pid = store.create_plan(gid)
        plan = store.get_plan(pid)
        assert plan is not None
        assert plan.goal_id == gid


class TestSteps:
    def test_create_and_list_steps(self, store):
        sid = store.create_session()
        gid = store.create_goal(sid, "obj")
        pid = store.create_plan(gid)
        store.create_step(
            pid,
            order_index=0,
            title="Read file",
            action="read_file",
            expected_output="file contents",
            verification_method="check non-empty",
            done_condition="output != ''",
        )
        steps = store.list_steps(pid)
        assert len(steps) == 1
        assert steps[0].title == "Read file"

    def test_update_step_status(self, store):
        sid = store.create_session()
        gid = store.create_goal(sid, "obj")
        pid = store.create_plan(gid)
        stid = store.create_step(pid, order_index=0, title="s", action="a", expected_output="x", verification_method="v", done_condition="d")
        store.update_step_status(stid, "done")
        assert store.get_step(stid).status == "done"


class TestCheckpoints:
    def test_record_and_list(self, store):
        sid = store.create_session()
        store.record_checkpoint(sid, phase="init", status="ok")
        store.record_checkpoint(sid, phase="done", status="completed")
        cps = store.list_checkpoints(sid)
        assert len(cps) == 2
        assert cps[0]["phase"] == "init"

    def test_latest_checkpoint(self, store):
        sid = store.create_session()
        store.record_checkpoint(sid, phase="init", status="ok")
        store.record_checkpoint(sid, phase="final", status="done")
        latest = store.latest_checkpoint(sid)
        assert latest["phase"] == "final"


class TestLoops:
    def test_create_loop(self, store):
        sid = store.create_session()
        lid = store.create_loop(sid, "check status", interval_seconds=60, max_iterations=10)
        loop = store.get_loop(lid)
        assert loop["prompt"] == "check status"

    def test_list_loops_by_session(self, store):
        s1 = store.create_session()
        s2 = store.create_session()
        store.create_loop(s1, "loop1", interval_seconds=30, max_iterations=5)
        store.create_loop(s2, "loop2", interval_seconds=60, max_iterations=10)
        assert len(store.list_loops(s1)) == 1
        assert len(store.list_loops(s2)) == 1
        assert len(store.list_loops()) == 2

    def test_record_tick(self, store):
        sid = store.create_session()
        lid = store.create_loop(sid, "tick", interval_seconds=10, max_iterations=5)
        store.record_loop_tick(lid)
        loop = store.get_loop(lid)
        assert loop["iterations"] == 1

    def test_record_tick_failure(self, store):
        sid = store.create_session()
        lid = store.create_loop(sid, "tick", interval_seconds=10, max_iterations=5)
        store.record_loop_tick(lid, failed=True)
        store.record_loop_tick(lid, failed=True)
        loop = store.get_loop(lid)
        assert loop["iterations"] == 2
        assert loop["consecutive_failures"] == 2


class TestSchedules:
    def test_create_schedule(self, store):
        sid = store.create_session()
        lid = store.create_loop(sid, "task", interval_seconds=60, max_iterations=10)
        sch_id = store.create_schedule(loop_id=lid, expression="*/5 * * * *", next_run_at="2026-01-01T00:00:00")
        sch = store.get_schedule(sch_id)
        assert sch["expression"] == "*/5 * * * *"

    def test_update_next_run(self, store):
        sid = store.create_session()
        lid = store.create_loop(sid, "task", interval_seconds=60, max_iterations=10)
        sch_id = store.create_schedule(loop_id=lid, expression="* * * * *", next_run_at="2026-01-01")
        store.update_schedule_next_run(sch_id, "2026-01-02")
        assert store.get_schedule(sch_id)["next_run_at"] == "2026-01-02"


class TestTokenUsage:
    def test_record_and_get(self, store):
        sid = store.create_session()
        store.record_token_usage(sid, prompt_tokens=100, completion_tokens=50, total_tokens=150, model="glm-4.7-flash")
        usage = store.get_token_usage(sid)
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150
        assert usage["api_calls"] == 1

    def test_accumulates_across_calls(self, store):
        sid = store.create_session()
        store.record_token_usage(sid, prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m1")
        store.record_token_usage(sid, prompt_tokens=200, completion_tokens=100, total_tokens=300, model="m1")
        usage = store.get_token_usage(sid)
        assert usage["prompt_tokens"] == 300
        assert usage["api_calls"] == 2

    def test_empty_session(self, store):
        sid = store.create_session()
        usage = store.get_token_usage(sid)
        assert usage["total_tokens"] == 0
        assert usage["api_calls"] == 0
