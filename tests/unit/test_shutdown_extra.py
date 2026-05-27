"""Tests for metis/runtime/shutdown.py - request_shutdown and shutdown_reason."""

from __future__ import annotations

import importlib

from metis.runtime import shutdown as shutdown_mod


def _reset_module():
    """Reset module globals between tests to avoid state leakage."""
    shutdown_mod._shutdown_requested = False
    shutdown_mod._shutdown_reason = ""
    shutdown_mod._pending_state = None
    shutdown_mod._pending_session_id = ""


def test_request_shutdown_sets_flag():
    _reset_module()
    assert not shutdown_mod.is_shutdown_requested()
    shutdown_mod.request_shutdown("manual")
    assert shutdown_mod.is_shutdown_requested()
    assert shutdown_mod.shutdown_reason() == "manual"
    _reset_module()


def test_request_shutdown_default_reason():
    _reset_module()
    shutdown_mod.request_shutdown()
    assert shutdown_mod.shutdown_reason() == "manual"
    _reset_module()


def test_request_shutdown_custom_reason():
    _reset_module()
    shutdown_mod.request_shutdown("timeout")
    assert shutdown_mod.shutdown_reason() == "timeout"
    assert shutdown_mod.is_shutdown_requested()
    _reset_module()


def test_shutdown_reason_initially_empty():
    _reset_module()
    assert shutdown_mod.shutdown_reason() == ""
    _reset_module()


def test_register_shutdown_handler_stores_state():
    _reset_module()
    fake_state = object()
    shutdown_mod.register_shutdown_handler(state=fake_state, session_id="sess-123")
    assert shutdown_mod._pending_state is fake_state
    assert shutdown_mod._pending_session_id == "sess-123"
    _reset_module()
