import pytest

from metis.loops.loop_manager import LoopManager
from metis.state.sqlite_store import SQLiteStateStore


class DummyController:
    def __init__(self):
        self.prompts = []

    async def run_prompt(self, *, session_id: str, prompt: str):
        self.prompts.append((session_id, prompt))
        return "ok"


@pytest.mark.asyncio
async def test_loop_manager_runs_until_max_iterations(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    controller = DummyController()
    manager = LoopManager(state=state, execution_controller=controller)
    spec = manager.create(session_id=session_id, prompt="tick", interval_seconds=0, max_iterations=2)

    manager.start(spec.id)
    await manager.wait(spec.id)

    updated = manager.get(spec.id)
    assert updated.status == "complete"
    assert updated.iterations == 2
    assert controller.prompts == [(session_id, "tick"), (session_id, "tick")]


@pytest.mark.asyncio
async def test_loop_manager_stop_cancels_running_loop(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    manager = LoopManager(state=state, execution_controller=DummyController())
    spec = manager.create(session_id=session_id, prompt="tick", interval_seconds=10, max_iterations=10)

    manager.start(spec.id)
    manager.stop(spec.id)
    await manager.wait(spec.id)

    assert manager.get(spec.id).status == "stopped"
