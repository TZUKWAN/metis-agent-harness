from datetime import datetime

from metis.loops.scheduler import SchedulerStore
from metis.state.sqlite_store import SQLiteStateStore


def test_scheduler_store_persists_schedule(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    loop_id = state.create_loop(session_id, "tick", interval_seconds=60, max_iterations=2)
    store = SchedulerStore(state)

    schedule = store.create(loop_id=loop_id, expression="every 10 minutes", now=datetime(2026, 1, 1, 10, 0))

    assert schedule.next_run_at == "2026-01-01T10:10:00"
    assert store.get(schedule.id) == schedule
    assert store.list(loop_id) == [schedule]
