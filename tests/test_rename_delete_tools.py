"""Tests for rename_file and delete_file tools."""

from metis.tools.workspace_tools import register_workspace_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def test_rename_file(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("hello")
    result = spec.handler({"old_path": "old.txt", "new_path": "new.txt"}, ToolContext())
    assert result["renamed"]
    assert (tmp_path / "new.txt").exists()
    assert not (tmp_path / "old.txt").exists()


def test_rename_file_source_not_found(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("rename_file")
    result = spec.handler({"old_path": "missing.txt", "new_path": "new.txt"}, ToolContext())
    assert "error" in result


def test_rename_file_security(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("data")
    result = spec.handler({"old_path": "old.txt", "new_path": ".env"}, ToolContext())
    assert "error" in result


def test_rename_file_creates_parent(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("rename_file")
    (tmp_path / "file.txt").write_text("data")
    result = spec.handler({"old_path": "file.txt", "new_path": "sub/dir/file.txt"}, ToolContext())
    assert result["renamed"]


def test_delete_file(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("delete_file")
    (tmp_path / "temp.txt").write_text("temporary")
    result = spec.handler({"path": "temp.txt"}, ToolContext())
    assert result["deleted"]
    assert not (tmp_path / "temp.txt").exists()


def test_delete_file_not_found(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("delete_file")
    result = spec.handler({"path": "missing.txt"}, ToolContext())
    assert "error" in result


def test_delete_file_security(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("delete_file")
    (tmp_path / ".env").write_text("secret")
    result = spec.handler({"path": ".env"}, ToolContext())
    assert "error" in result


def test_delete_file_cannot_delete_dir(tmp_path):
    registry = ToolRegistry()
    register_workspace_tools(registry, workspace=str(tmp_path))
    spec = registry.get("delete_file")
    (tmp_path / "subdir").mkdir()
    result = spec.handler({"path": "subdir"}, ToolContext())
    assert "error" in result
