"""Tests for tree_summary tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_tree_summary_basic():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "src", "main.py").write_text("")
        Path(tmp, "src", "utils").mkdir()
        Path(tmp, "src", "utils", "helpers.py").write_text("")
        Path(tmp, "README.md").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("tree_summary").handler
        result = handler({"path": "."}, _make_ctx())
        tree = result["tree"]
        assert "README.md" in tree
        assert "src/" in tree
        assert "main.py" in tree
        assert "utils/" in tree
        assert "helpers.py" in tree
        assert result["total_files"] >= 2
        assert result["total_dirs"] >= 2


def test_tree_summary_respects_max_depth():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a", "b", "c", "d").mkdir(parents=True)
        Path(tmp, "a", "b", "c", "d", "file.txt").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("tree_summary").handler
        result = handler({"path": ".", "max_depth": 2}, _make_ctx())
        assert result["max_depth"] == 2


def test_tree_summary_hides_hidden():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".git").mkdir()
        Path(tmp, "visible").mkdir()
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("tree_summary").handler
        result = handler({"path": "."}, _make_ctx())
        assert ".git" not in result["tree"]
        assert "visible/" in result["tree"]


def test_tree_summary_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("tree_summary").handler
        result = handler({"path": "nonexistent"}, _make_ctx())
        assert "error" in result


def test_tree_summary_max_entries():
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(10):
            Path(tmp, f"f{i}.txt").write_text("")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("tree_summary").handler
        result = handler({"path": ".", "max_entries": 5}, _make_ctx())
        assert "..." in result["tree"]
