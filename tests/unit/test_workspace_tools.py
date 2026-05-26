"""Unit tests for workspace navigation tools."""

import pytest

from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext
from metis.tools.workspace_tools import register_workspace_tools


@pytest.fixture
def registry(tmp_path):
    reg = ToolRegistry()
    register_workspace_tools(reg, workspace=str(tmp_path))
    return reg


@pytest.fixture
def context():
    return ToolContext(session_id="test", workspace=".", allowed_tools=None)


def test_list_dir_registered(registry):
    assert "list_dir" in registry.list_tools()


def test_search_files_registered(registry):
    assert "search_files" in registry.list_tools()


def test_append_to_file_registered(registry):
    assert "append_to_file" in registry.list_tools()


def test_list_dir_basic(registry, context, tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "b.py").write_text("x=1", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()

    tool = registry.get("list_dir")
    result = tool.handler({"path": "."}, context)
    names = [e["name"] for e in result["entries"]]
    assert "a.txt" in names
    assert "b.py" in names
    assert "sub" in names
    file_entry = next(e for e in result["entries"] if e["name"] == "a.txt")
    assert file_entry["type"] == "file"
    assert file_entry["size"] == 5


def test_list_dir_not_found(registry, context):
    tool = registry.get("list_dir")
    result = tool.handler({"path": "nonexistent"}, context)
    assert "error" in result


def test_search_files_pattern(registry, context, tmp_path):
    (tmp_path / "app.py").write_text("code", encoding="utf-8")
    (tmp_path / "test.py").write_text("test", encoding="utf-8")
    (tmp_path / "readme.md").write_text("doc", encoding="utf-8")

    tool = registry.get("search_files")
    result = tool.handler({"pattern": "*.py"}, context)
    paths = [f["path"] for f in result["files"]]
    assert "app.py" in paths
    assert "test.py" in paths
    assert "readme.md" not in paths


def test_search_files_in_subdir(registry, context, tmp_path):
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("main", encoding="utf-8")

    tool = registry.get("search_files")
    result = tool.handler({"pattern": "*.py", "path": "src"}, context)
    assert any("main.py" in f["path"] for f in result["files"])


def test_append_to_file_creates_new(registry, context, tmp_path):
    tool = registry.get("append_to_file")
    result = tool.handler({"path": "new.txt", "content": "first line\n"}, context)
    assert result["created"] is True
    content = (tmp_path / "new.txt").read_text(encoding="utf-8")
    assert content == "first line\n"


def test_append_to_file_appends_existing(registry, context, tmp_path):
    (tmp_path / "log.txt").write_text("line1\n", encoding="utf-8")
    tool = registry.get("append_to_file")
    result = tool.handler({"path": "log.txt", "content": "line2\n"}, context)
    assert result["created"] is False
    assert result["appended"] is True
    content = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert content == "line1\nline2\n"
