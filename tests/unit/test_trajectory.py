import json

from metis.telemetry.trajectory import TrajectoryRecorder


def test_trajectory_recorder_exports_jsonl(tmp_path):
    recorder = TrajectoryRecorder()
    recorder.record("tool.call", {"tool": "read_file"})
    path = tmp_path / "trajectory.jsonl"

    recorder.export_jsonl(path)

    assert json.loads(path.read_text(encoding="utf-8"))["event_type"] == "tool.call"
