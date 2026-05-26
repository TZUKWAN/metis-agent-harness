"""Tests for per-session tool call limit."""

from __future__ import annotations

import pytest

from metis.config import MAX_TOOLS_PER_SESSION


def test_max_tools_per_session_has_reasonable_value():
    assert isinstance(MAX_TOOLS_PER_SESSION, int)
    assert MAX_TOOLS_PER_SESSION >= 50


def test_max_tools_per_session_is_finite():
    assert MAX_TOOLS_PER_SESSION <= 10_000


def test_import_from_config():
    from metis.config import MAX_TOOLS_PER_SESSION as limit
    assert limit == MAX_TOOLS_PER_SESSION
