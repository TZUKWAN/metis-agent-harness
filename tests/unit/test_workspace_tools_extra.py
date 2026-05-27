"""Extra unit tests for workspace_tools to increase coverage."""

import os
from pathlib import Path

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


# list_dir uncovered lines: 20, 30-31

def test_list_dir_path_outside_workspace(registry, context):
    """Line 20: path outside workspace returns error."""
    tool = registry.get("list_dir")
    result = tool.handler({"path": "../outside"}, context)
    assert result["error"] == "Path outside workspace"
    assert result["entries"] == []


def test_list_dir_oserror_on_stat(registry, context, tmp_path, monkeypatch):
    """Lines 30-31: OSError when getting file size is silently ignored."""
    tool = registry.get("list_dir")
    (tmp_path / "unstatable.txt").write_text("x", encoding="utf-8")

    original_stat = Path.stat

    def bad_stat(self, *args, **kwargs):
        if self.name == "unstatable.txt":
            raise OSError("boom")
        return original_stat(self, *args, **kwargs)

    # Prevent is_dir() and is_file() from calling stat() so only the explicit
    # item.stat() in list_dir triggers the OSError.
    monkeypatch.setattr(Path, "is_dir", lambda self: self.name != "unstatable.txt")
    monkeypatch.setattr(Path, "is_file", lambda self: self.name == "unstatable.txt")
    monkeypatch.setattr(Path, "stat", bad_stat)
    result = tool.handler({"path": "."}, context)
    entry = next(e for e in result["entries"] if e["name"] == "unstatable.txt")
    assert entry["type"] == "file"
    assert "size" not in entry


# search_files uncovered lines: 43, 45, 54-55

def test_search_files_path_outside_workspace(registry, context):
    """Line 43: path outside workspace returns error."""
    tool = registry.get("search_files")
    result = tool.handler({"pattern": "*.py", "path": "../outside"}, context)
    assert result["error"] == "Path outside workspace"
    assert result["files"] == []


def test_search_files_path_not_found(registry, context):
    """Line 45: path not found returns error."""
    tool = registry.get("search_files")
    result = tool.handler({"pattern": "*.py", "path": "nonexistent_dir"}, context)
    assert result["error"] == "Path not found: nonexistent_dir"
    assert result["files"] == []


def test_search_files_relative_to_valueerror(registry, context, tmp_path, monkeypatch):
    """Lines 54-55: ValueError from relative_to causes skip."""
    tool = registry.get("search_files")
    (tmp_path / "a.py").write_text("x", encoding="utf-8")

    original_relative_to = Path.relative_to

    def bad_relative_to(self, other):
        if self.name == "a.py":
            raise ValueError("outside root")
        return original_relative_to(self, other)

    monkeypatch.setattr(Path, "relative_to", bad_relative_to)
    result = tool.handler({"pattern": "*.py"}, context)
    assert result["files"] == []


# append_to_file uncovered lines: 65, 68

def test_append_to_file_path_outside_workspace(registry, context):
    """Line 65: path outside workspace returns error."""
    tool = registry.get("append_to_file")
    result = tool.handler({"path": "../outside.txt", "content": "hello"}, context)
    assert result["error"] == "Path outside workspace"


def test_append_to_file_write_denied(registry, context):
    """Line 68: write denied for security returns error."""
    tool = registry.get("append_to_file")
    result = tool.handler({"path": ".env", "content": "secret"}, context)
    assert result["error"] == "Write denied for security: .env"


# rename_file uncovered lines: 77-90

def test_rename_file_success(registry, context, tmp_path):
    """Lines 77-90: successful rename."""
    tool = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("content", encoding="utf-8")
    result = tool.handler({"old_path": "old.txt", "new_path": "new.txt"}, context)
    assert result["renamed"] is True
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"


def test_rename_file_path_outside_workspace_old(registry, context):
    """Line 81-82: old_path outside workspace returns error."""
    tool = registry.get("rename_file")
    result = tool.handler({"old_path": "../outside.txt", "new_path": "new.txt"}, context)
    assert result["error"] == "Path outside workspace"


def test_rename_file_path_outside_workspace_new(registry, context, tmp_path):
    """Line 81-82: new_path outside workspace returns error."""
    tool = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("x", encoding="utf-8")
    result = tool.handler({"old_path": "old.txt", "new_path": "../outside.txt"}, context)
    assert result["error"] == "Path outside workspace"


def test_rename_file_write_denied(registry, context, tmp_path):
    """Lines 84-85: write denied for security returns error."""
    tool = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("x", encoding="utf-8")
    result = tool.handler({"old_path": "old.txt", "new_path": ".env"}, context)
    assert result["error"] == "Write denied for security"


def test_rename_file_source_not_found(registry, context):
    """Lines 86-87: source not found returns error."""
    tool = registry.get("rename_file")
    result = tool.handler({"old_path": "missing.txt", "new_path": "new.txt"}, context)
    assert result["error"] == "Source not found: missing.txt"


def test_rename_file_creates_parent_dirs(registry, context, tmp_path):
    """Line 88: rename creates parent directories if needed."""
    tool = registry.get("rename_file")
    (tmp_path / "old.txt").write_text("x", encoding="utf-8")
    result = tool.handler({"old_path": "old.txt", "new_path": "sub/dir/new.txt"}, context)
    assert result["renamed"] is True
    assert (tmp_path / "sub" / "dir" / "new.txt").exists()


# delete_file uncovered lines: 93-105

def test_delete_file_success(registry, context, tmp_path):
    """Lines 93-105: successful file deletion."""
    tool = registry.get("delete_file")
    (tmp_path / "to_delete.txt").write_text("bye", encoding="utf-8")
    result = tool.handler({"path": "to_delete.txt"}, context)
    assert result["deleted"] is True
    assert not (tmp_path / "to_delete.txt").exists()


def test_delete_file_path_outside_workspace(registry, context):
    """Lines 95-96: path outside workspace returns error."""
    tool = registry.get("delete_file")
    result = tool.handler({"path": "../outside.txt"}, context)
    assert result["error"] == "Path outside workspace"


def test_delete_file_write_denied(registry, context):
    """Lines 98-99: write denied for security returns error."""
    tool = registry.get("delete_file")
    result = tool.handler({"path": ".env"}, context)
    assert result["error"] == "Write denied for security: .env"


def test_delete_file_not_found(registry, context):
    """Lines 100-101: file not found returns error."""
    tool = registry.get("delete_file")
    result = tool.handler({"path": "missing.txt"}, context)
    assert result["error"] == "File not found: missing.txt"


def test_delete_file_is_directory(registry, context, tmp_path):
    """Lines 102-103: cannot delete directories."""
    tool = registry.get("delete_file")
    (tmp_path / "subdir").mkdir()
    result = tool.handler({"path": "subdir"}, context)
    assert result["error"] == "Cannot delete directories, only files"


# mkdir uncovered lines: 108-117

def test_mkdir_success(registry, context, tmp_path):
    """Lines 108-117: successful directory creation."""
    tool = registry.get("mkdir")
    result = tool.handler({"path": "new_dir"}, context)
    assert result["created"] is True
    assert (tmp_path / "new_dir").is_dir()


def test_mkdir_already_exists(registry, context, tmp_path):
    """Lines 115-117: mkdir on existing directory returns created=False."""
    tool = registry.get("mkdir")
    (tmp_path / "existing").mkdir()
    result = tool.handler({"path": "existing"}, context)
    assert result["created"] is False


def test_mkdir_path_outside_workspace(registry, context):
    """Lines 110-111: path outside workspace returns error."""
    tool = registry.get("mkdir")
    result = tool.handler({"path": "../outside"}, context)
    assert result["error"] == "Path outside workspace"


def test_mkdir_write_denied(registry, context):
    """Lines 113-114: write denied for security returns error."""
    tool = registry.get("mkdir")
    result = tool.handler({"path": ".env"}, context)
    assert result["error"] == "Write denied for security: .env"


def test_mkdir_nested(registry, context, tmp_path):
    """Lines 116-117: nested directory creation."""
    tool = registry.get("mkdir")
    result = tool.handler({"path": "a/b/c"}, context)
    assert result["created"] is True
    assert (tmp_path / "a" / "b" / "c").is_dir()


# copy_file uncovered lines: 120-136

def test_copy_file_success(registry, context, tmp_path):
    """Lines 120-136: successful file copy."""
    tool = registry.get("copy_file")
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    result = tool.handler({"source": "src.txt", "destination": "dst.txt"}, context)
    assert result["copied"] is True
    assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "hello"
    assert result["size"] == 5


def test_copy_file_path_outside_workspace_src(registry, context):
    """Lines 125-126: source outside workspace returns error."""
    tool = registry.get("copy_file")
    result = tool.handler({"source": "../outside.txt", "destination": "dst.txt"}, context)
    assert result["error"] == "Path outside workspace"


def test_copy_file_path_outside_workspace_dst(registry, context, tmp_path):
    """Lines 125-126: destination outside workspace returns error."""
    tool = registry.get("copy_file")
    (tmp_path / "src.txt").write_text("x", encoding="utf-8")
    result = tool.handler({"source": "src.txt", "destination": "../outside.txt"}, context)
    assert result["error"] == "Path outside workspace"


def test_copy_file_read_denied(registry, context, tmp_path):
    """Lines 128-129: read denied for security returns error."""
    tool = registry.get("copy_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    result = tool.handler({"source": ".env", "destination": "copy.txt"}, context)
    assert result["error"] == "Read denied for security: .env"


def test_copy_file_write_denied(registry, context, tmp_path):
    """Lines 130-131: write denied for security returns error."""
    tool = registry.get("copy_file")
    (tmp_path / "src.txt").write_text("x", encoding="utf-8")
    result = tool.handler({"source": "src.txt", "destination": ".env"}, context)
    assert result["error"] == "Write denied for security: .env"


def test_copy_file_source_not_found(registry, context):
    """Lines 132-133: source not found returns error."""
    tool = registry.get("copy_file")
    result = tool.handler({"source": "missing.txt", "destination": "dst.txt"}, context)
    assert result["error"] == "Source not found: missing.txt"


def test_copy_file_creates_parent_dirs(registry, context, tmp_path):
    """Lines 134-135: copy creates parent directories if needed."""
    tool = registry.get("copy_file")
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    result = tool.handler({"source": "src.txt", "destination": "sub/dir/dst.txt"}, context)
    assert result["copied"] is True
    assert (tmp_path / "sub" / "dir" / "dst.txt").exists()
