"""Extra tests for metis/config.py validate_config to cover all warning branches."""

from __future__ import annotations

import metis.config as cfg
from metis.config import validate_config


def test_validate_config_no_warnings_by_default():
    warnings = validate_config()
    assert warnings == [], f"Unexpected warnings: {warnings}"


def test_validate_config_catches_max_content_length_too_small(monkeypatch):
    monkeypatch.setattr(cfg, "MAX_CONTENT_LENGTH", 100)
    warnings = validate_config()
    assert any("MAX_CONTENT_LENGTH" in w for w in warnings)


def test_validate_config_catches_max_timeout_too_small(monkeypatch):
    monkeypatch.setattr(cfg, "MAX_TIMEOUT", 2)
    warnings = validate_config()
    assert any("MAX_TIMEOUT" in w for w in warnings)


def test_validate_config_catches_per_turn_timeout_too_small(monkeypatch):
    monkeypatch.setattr(cfg, "PER_TURN_TIMEOUT", 1)
    warnings = validate_config()
    assert any("PER_TURN_TIMEOUT" in w for w in warnings)


def test_validate_config_catches_tool_execution_timeout_too_small(monkeypatch):
    monkeypatch.setattr(cfg, "TOOL_EXECUTION_TIMEOUT", 0)
    warnings = validate_config()
    assert any("TOOL_EXECUTION_TIMEOUT" in w for w in warnings)


def test_validate_config_catches_tool_execution_exceeds_max_timeout(monkeypatch):
    monkeypatch.setattr(cfg, "TOOL_EXECUTION_TIMEOUT", 700)
    warnings = validate_config()
    assert any("TOOL_EXECUTION_TIMEOUT" in w and "exceeds" in w for w in warnings)


def test_validate_config_catches_max_tools_per_session_lt_1(monkeypatch):
    monkeypatch.setattr(cfg, "MAX_TOOLS_PER_SESSION", 0)
    warnings = validate_config()
    assert any("MAX_TOOLS_PER_SESSION" in w for w in warnings)


def test_validate_config_catches_context_chars_per_token_lt_1(monkeypatch):
    monkeypatch.setattr(cfg, "CONTEXT_CHARS_PER_TOKEN", 0)
    warnings = validate_config()
    assert any("CONTEXT_CHARS_PER_TOKEN" in w for w in warnings)


def test_validate_config_catches_context_threshold_too_low(monkeypatch):
    monkeypatch.setattr(cfg, "CONTEXT_THRESHOLD", 0.05)
    warnings = validate_config()
    assert any("CONTEXT_THRESHOLD" in w for w in warnings)


def test_validate_config_catches_max_tool_repair_retries_negative(monkeypatch):
    monkeypatch.setattr(cfg, "MAX_TOOL_REPAIR_RETRIES", -1)
    warnings = validate_config()
    assert any("MAX_TOOL_REPAIR_RETRIES" in w for w in warnings)


def test_validate_config_catches_max_parser_repair_retries_negative(monkeypatch):
    monkeypatch.setattr(cfg, "MAX_PARSER_REPAIR_RETRIES", -1)
    warnings = validate_config()
    assert any("MAX_PARSER_REPAIR_RETRIES" in w for w in warnings)


def test_validate_config_catches_empty_model(monkeypatch):
    monkeypatch.setattr(cfg, "DEFAULT_MODEL", "")
    warnings = validate_config()
    assert any("DEFAULT_MODEL" in w for w in warnings)


def test_validate_config_catches_unrecognized_profile(monkeypatch):
    monkeypatch.setattr(cfg, "DEFAULT_PROFILE", "unknown_profile")
    warnings = validate_config()
    assert any("DEFAULT_PROFILE" in w for w in warnings)
