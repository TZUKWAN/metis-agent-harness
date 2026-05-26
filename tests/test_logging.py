"""Tests for metis/logging.py."""

import logging
import os

from metis.logging import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "metis.test_module"


def test_get_logger_has_handler():
    logger = get_logger("handler_test")
    assert len(logger.handlers) >= 1


def test_get_logger_idempotent():
    logger1 = get_logger("idem")
    count = len(logger1.handlers)
    logger2 = get_logger("idem")
    assert len(logger2.handlers) == count


def test_different_names_different_loggers():
    a = get_logger("alpha")
    b = get_logger("beta")
    assert a.name != b.name
