from metis.loops.loop_manager import LoopManager
from metis.state.sqlite_store import SQLiteStateStore


def test_loop_spec_can_be_created_and_listed(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    manager = LoopManager(state=state)

    spec = manager.create(session_id=session_id, prompt="run checks", interval_seconds=1.5, max_iterations=3)

    assert spec.prompt == "run checks"
    assert spec.status == "created"
    assert manager.get(spec.id).max_iterations == 3
    assert manager.list(session_id) == [spec]
