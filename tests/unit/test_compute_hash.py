"""Tests for compute_hash tool."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(session_id="test", workspace=".", allowed_tools=None, allowed_tool_permissions=None, hooks=None, state=None)


def test_compute_hash_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("hello world")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("compute_hash").handler
        result = handler({"path": "test.txt"}, _make_ctx())
        assert result["algorithm"] == "sha256"
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert result["hash"] == expected
        assert result["file_size"] == 11


def test_compute_hash_md5():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("test")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("compute_hash").handler
        result = handler({"path": "test.txt", "algorithm": "md5"}, _make_ctx())
        assert result["algorithm"] == "md5"
        expected = hashlib.md5(b"test").hexdigest()
        assert result["hash"] == expected


def test_compute_hash_sha1():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_bytes(b"\x00\x01\x02")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("compute_hash").handler
        result = handler({"path": "test.txt", "algorithm": "sha1"}, _make_ctx())
        assert len(result["hash"]) == 40


def test_compute_hash_unsupported_algorithm():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp, "test.txt")
        f.write_text("data")
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("compute_hash").handler
        result = handler({"path": "test.txt", "algorithm": "blake2"}, _make_ctx())
        assert "error" in result


def test_compute_hash_missing_file():
    with tempfile.TemporaryDirectory() as tmp:
        registry = ToolRegistry()
        register_builtin_tools(registry, workspace=tmp)
        handler = registry.get("compute_hash").handler
        result = handler({"path": "missing.txt"}, _make_ctx())
        assert "error" in result
