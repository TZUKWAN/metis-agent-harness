"""Tests for list_directory tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_list_directory_basic():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.py").write_text("print(1)")
        Path(tmp, "b.txt").write_text("hello")
        Path(tmp, "subdir").mkdir()
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": "."}, _make_ctx())
        assert result["count"] == 3
        names = [e["name"] for e in result["entries"]]
        assert "a.py" in names
        assert "b.txt" in names
        assert "subdir" in names


def test_list_directory_directories_first():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "zzz.py").write_text("")
        Path(tmp, "aaa_dir").mkdir()
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": "."}, _make_ctx())
        first = result["entries"][0]
        assert first["type"] == "directory"


def test_list_directory_hides_hidden():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".hidden").write_text("")
        Path(tmp, "visible.py").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": "."}, _make_ctx())
        names = [e["name"] for e in result["entries"]]
        assert "visible.py" in names
        assert ".hidden" not in names


def test_list_directory_show_hidden():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".hidden").write_text("")
        Path(tmp, "visible.py").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": ".", "show_hidden": True}, _make_ctx())
        names = [e["name"] for e in result["entries"]]
        assert "visible.py" in names
        assert ".hidden" in names


def test_list_directory_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": "nonexistent"}, _make_ctx())
        assert "error" in result


def test_list_directory_max_entries():
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(10):
            Path(tmp, f"file_{i}.txt").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("list_directory").handler
        result = handler({"path": ".", "max_entries": 5}, _make_ctx())
        assert result["count"] == 5
