"""Tests for metis/runtime/shutdown.py."""

from metis.runtime.shutdown import is_shutdown_requested


def test_initial_state_not_requested():
    # Import fresh to check default
    assert not is_shutdown_requested()


def test_is_shutdown_requested_returns_bool():
    result = is_shutdown_requested()
    assert isinstance(result, bool)
