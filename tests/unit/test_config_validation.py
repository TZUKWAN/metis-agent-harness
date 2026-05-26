"""Tests for config validation."""

from __future__ import annotations

from metis.config import validate_config


def test_validate_config_no_warnings():
    warnings = validate_config()
    assert warnings == [], f"Unexpected warnings: {warnings}"


def test_validate_config_returns_list():
    result = validate_config()
    assert isinstance(result, list)


def test_validate_config_catches_bad_max_turns(monkeypatch):
    import metis.config as cfg
    monkeypatch.setattr(cfg, "DEFAULT_MAX_TURNS", 0)
    warnings = validate_config()
    assert any("DEFAULT_MAX_TURNS" in w for w in warnings)


def test_validate_config_catches_bad_temperature(monkeypatch):
    import metis.config as cfg
    monkeypatch.setattr(cfg, "DEFAULT_TEMPERATURE", 5.0)
    warnings = validate_config()
    assert any("DEFAULT_TEMPERATURE" in w for w in warnings)


def test_validate_config_catches_per_turn_exceeds_max(monkeypatch):
    import metis.config as cfg
    monkeypatch.setattr(cfg, "PER_TURN_TIMEOUT", 700)
    warnings = validate_config()
    assert any("PER_TURN_TIMEOUT" in w for w in warnings)


def test_validate_config_catches_bad_port(monkeypatch):
    import metis.config as cfg
    monkeypatch.setattr(cfg, "DEFAULT_PORT", 99999)
    warnings = validate_config()
    assert any("DEFAULT_PORT" in w for w in warnings)
