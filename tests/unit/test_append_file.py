"""Tests for append_file tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_append_to_existing():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "log.txt")
        f.write_text("line1\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("append_file").handler
        result = handler({"path": "log.txt", "content": "line2\n"}, _make_ctx())
        assert result["appended"] is True
        assert f.read_text() == "line1\nline2\n"


def test_append_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("append_file").handler
        result = handler({"path": "new.txt", "content": "hello"}, _make_ctx())
        assert result["appended"] is True
        assert Path(tmp, "new.txt").read_text() == "hello"


def test_append_content_length():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("append_file").handler
        result = handler({"path": "f.txt", "content": "abc"}, _make_ctx())
        assert result["content_length"] == 3


def test_append_multiple_times():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("append_file").handler
        handler({"path": "f.txt", "content": "a"}, _make_ctx())
        handler({"path": "f.txt", "content": "b"}, _make_ctx())
        handler({"path": "f.txt", "content": "c"}, _make_ctx())
        assert Path(tmp, "f.txt").read_text() == "abc"
