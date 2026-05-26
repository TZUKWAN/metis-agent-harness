"""Tests for metis/config.py defaults."""

import metis.config as cfg


def test_default_model():
    assert cfg.DEFAULT_MODEL


def test_default_max_turns():
    assert cfg.DEFAULT_MAX_TURNS == 12


def test_default_temperature():
    assert cfg.DEFAULT_TEMPERATURE == 0.2


def test_max_content_length():
    assert cfg.MAX_CONTENT_LENGTH == 1_000_000


def test_max_timeout():
    assert cfg.MAX_TIMEOUT == 600


def test_per_turn_timeout():
    assert cfg.PER_TURN_TIMEOUT == 120


def test_tool_execution_timeout():
    assert cfg.TOOL_EXECUTION_TIMEOUT == 30


def test_max_tool_repair_retries():
    assert cfg.MAX_TOOL_REPAIR_RETRIES == 1


def test_default_host():
    assert cfg.DEFAULT_HOST == "127.0.0.1"


def test_default_port():
    assert cfg.DEFAULT_PORT == 8080


def test_default_profile():
    assert cfg.DEFAULT_PROFILE == "small"


def test_context_chars_per_token():
    assert cfg.CONTEXT_CHARS_PER_TOKEN == 4
