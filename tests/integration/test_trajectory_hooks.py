from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.telemetry.hooks import install_trajectory_hooks
from metis.telemetry.trajectory import TrajectoryRecorder


def test_trajectory_hooks_capture_hookbus_events(tmp_path):
    hooks = HookBus()
    recorder = install_trajectory_hooks(hooks, TrajectoryRecorder(), [EventType.AGENT_PRE_RUN])

    hooks.emit(EventType.AGENT_PRE_RUN, {"session_id": "s1"})
    path = tmp_path / "trajectory.jsonl"
    recorder.export_jsonl(path)

    assert "agent.pre_run" in path.read_text(encoding="utf-8")
