"""Tests for diff_files tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_diff_identical_files():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("line1\nline2\n")
        Path(tmp, "b.txt").write_text("line1\nline2\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("diff_files").handler
        result = handler({"path_a": "a.txt", "path_b": "b.txt"}, _make_ctx())
        assert result["diff_count"] == 0


def test_diff_different_files():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("same\ndiff_a\n")
        Path(tmp, "b.txt").write_text("same\ndiff_b\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("diff_files").handler
        result = handler({"path_a": "a.txt", "path_b": "b.txt"}, _make_ctx())
        assert result["diff_count"] == 1
        assert result["differences"][0]["a"] == "diff_a"
        assert result["differences"][0]["b"] == "diff_b"
        assert result["differences"][0]["line"] == 2


def test_diff_missing_file():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("hello")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("diff_files").handler
        result = handler({"path_a": "a.txt", "path_b": "missing.txt"}, _make_ctx())
        assert "error" in result


def test_diff_different_lengths():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("line1\n")
        Path(tmp, "b.txt").write_text("line1\nline2\nline3\n")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("diff_files").handler
        result = handler({"path_a": "a.txt", "path_b": "b.txt"}, _make_ctx())
        assert result["lines_a"] == 1
        assert result["lines_b"] == 3
        assert result["diff_count"] >= 1
