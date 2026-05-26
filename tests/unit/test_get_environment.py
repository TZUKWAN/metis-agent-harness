"""Tests for get_environment tool."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_get_environment_returns_basic_info():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("get_environment").handler
        result = handler({}, _make_ctx())
        assert "python_version" in result
        assert "platform" in result
        assert "cwd" in result


def test_get_environment_python_version_format():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("get_environment").handler
        result = handler({}, _make_ctx())
        version = result["python_version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


def test_get_environment_lists_packages():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("get_environment").handler
        result = handler({}, _make_ctx())
        assert "packages_count" in result
        assert isinstance(result["packages_count"], int)


def test_get_environment_workspace_structure():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "README.md").write_text("test")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("get_environment").handler
        result = handler({"path": "."}, _make_ctx())
        assert "workspace_top_entries" in result
        entries = result["workspace_top_entries"]
        assert "src" in entries
        assert "README.md" in entries
