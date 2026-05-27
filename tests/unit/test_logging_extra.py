"""Extra tests for metis/logging.py - JSON format and structured formatter."""

from __future__ import annotations

import logging
import os

from metis.logging import _StructuredFormatter, get_logger


def test_json_format_uses_structured_formatter(monkeypatch):
    monkeypatch.setenv("METIS_LOG_FORMAT", "json")
    monkeypatch.setenv("METIS_LOG_LEVEL", "DEBUG")
    # Use a fresh name so the logger is created anew
    logger_name = "json_test_extra"
    full_name = f"metis.{logger_name}"
    # Clear any pre-existing logger
    existing = logging.getLogger(full_name)
    existing.handlers.clear()

    logger = get_logger(logger_name)
    assert logger.handlers
    handler = logger.handlers[-1]
    assert isinstance(handler.formatter, _StructuredFormatter)
    # Cleanup
    logger.handlers.clear()


def test_structured_formatter_produces_valid_json():
    import json

    formatter = _StructuredFormatter()
    record = logging.LogRecord(
        name="metis.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=None,
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "hello world"
    assert "timestamp" in data


def test_structured_formatter_with_exception():
    import json

    formatter = _StructuredFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="metis.test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=1,
        msg="error occurred",
        args=None,
        exc_info=exc_info,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert "exception" in data
    assert "ValueError" in data["exception"]
    assert "boom" in data["exception"]


def test_get_logger_default_text_format():
    # Default format is text (METIS_LOG_FORMAT not set or "text")
    logger_name = "text_test_extra"
    full_name = f"metis.{logger_name}"
    existing = logging.getLogger(full_name)
    existing.handlers.clear()

    logger = get_logger(logger_name)
    handler = logger.handlers[-1]
    assert not isinstance(handler.formatter, _StructuredFormatter)
    assert isinstance(handler.formatter, logging.Formatter)
    logger.handlers.clear()


def test_structured_formatter_no_exception():
    import json

    formatter = _StructuredFormatter()
    record = logging.LogRecord(
        name="metis.test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="just a warning",
        args=None,
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert "exception" not in data
    assert data["level"] == "WARNING"
