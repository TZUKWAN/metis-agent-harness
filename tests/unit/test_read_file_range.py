"""Tests for read_file_range tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_read_file_range_basic():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("read_file_range").handler
        result = handler({"path": "test.txt", "offset": 1, "limit": 2}, _make_ctx())
        assert result["lines_returned"] == 2
        assert result["total_lines"] == 5
        assert "line2" in result["content"]
        assert "line3" in result["content"]
        assert result["numbered"]["2"] == "line2"
        assert result["numbered"]["3"] == "line3"


def test_read_file_range_default_offset():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("aaa\nbbb\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("read_file_range").handler
        result = handler({"path": "test.txt"}, _make_ctx())
        assert result["offset"] == 0
        assert result["lines_returned"] == 2


def test_read_file_range_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("read_file_range").handler
        result = handler({"path": "missing.txt"}, _make_ctx())
        assert "error" in result


def test_read_file_range_beyond_end():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("a\nb\nc\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("read_file_range").handler
        result = handler({"path": "test.txt", "offset": 10, "limit": 5}, _make_ctx())
        assert result["lines_returned"] == 0
