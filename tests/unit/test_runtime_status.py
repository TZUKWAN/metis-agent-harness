from metis.runtime.status import RuntimeStatus


def test_runtime_status_maps_strict_output_status_to_runtime_and_step():
    assert RuntimeStatus.from_strict_status("done") == RuntimeStatus.FINAL
    assert RuntimeStatus.from_strict_status("blocked") == RuntimeStatus.BLOCKED
    assert RuntimeStatus.from_strict_status("needs_more_work") == RuntimeStatus.NEEDS_MORE_WORK
    assert RuntimeStatus.BLOCKED.step_status == "blocked"
    assert RuntimeStatus.NEEDS_MORE_WORK.step_status == "needs_more_work"
