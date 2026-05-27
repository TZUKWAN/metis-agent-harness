"""Extra unit tests for builtin tool handlers to increase coverage.

These tests exercise the actual tool handler functions registered by
register_builtin_tools(), using real files and real arguments.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from metis.tools.builtin import (
    ALLOWED_COMMANDS,
    DANGEROUS_PATTERNS,
    _check_dangerous_patterns,
    _strip_ansi,
    _validate_command,
    register_builtin_tools,
)
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext
from metis.runtime.response import ToolCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry(tmp_path):
    """Create a ToolRegistry with builtin tools rooted at tmp_path."""
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    return registry


async def _dispatch(registry, name, args, ctx=None):
    """Dispatch a tool call and return the result object."""
    dispatcher = ToolDispatcher(registry)
    return await dispatcher.dispatch(
        ToolCall(name=name, arguments=args, id="call1"),
        ctx or ToolContext(),
    )


def _get_handler(registry, name):
    """Get the raw handler function for a tool."""
    spec = registry.get(name)
    assert spec is not None, f"Tool {name} not found in registry"
    return spec.handler


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def test_strip_ansi():
    assert _strip_ansi("\x1b[31mhello\x1b[0m") == "hello"
    assert _strip_ansi("no ansi") == "no ansi"


def test_validate_command_empty():
    assert _validate_command([]) == "Empty command"


def test_validate_command_not_allowed():
    assert _validate_command(["rm", "-rf", "/"]) == "Command not in allowlist: rm"


def test_validate_command_allowed():
    assert _validate_command(["python", "--version"]) is None


def test_check_dangerous_patterns_blocks():
    assert _check_dangerous_patterns("rm -rf /") is not None
    assert _check_dangerous_patterns("git push --force") is not None
    assert _check_dangerous_patterns("format C:") is not None


def test_check_dangerous_patterns_allows_safe():
    assert _check_dangerous_patterns("python --version") is None
    assert _check_dangerous_patterns("ls -la") is None


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_with_encoding(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")

    result = await _dispatch(registry, "read_file", {"path": "test.txt", "encoding": "utf-8"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["content"] == "hello world"
    assert data["encoding"] == "utf-8"


@pytest.mark.asyncio
async def test_read_file_auto_encoding_latin1(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.bin"
    # Write bytes that utf-8 cannot decode but latin-1 can
    f.write_bytes(b"\xe9\xe8\xe7")  # latin-1 characters

    result = await _dispatch(registry, "read_file", {"path": "test.bin", "encoding": "auto"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["encoding"] == "latin-1"


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_file_creates_backup(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "existing.txt"
    f.write_text("old content", encoding="utf-8")

    result = await _dispatch(registry, "write_file", {"path": "existing.txt", "content": "new content"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["written"] is True
    assert "backup" in data
    assert f.read_text(encoding="utf-8") == "new content"
    # backup should have old content
    backup = tmp_path / "existing.txt.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "old content"


@pytest.mark.asyncio
async def test_write_file_content_too_long(tmp_path):
    registry = _make_registry(tmp_path)
    from metis.config import MAX_CONTENT_LENGTH
    handler = _get_handler(registry, "write_file")

    with pytest.raises(ValueError, match="maximum length"):
        handler({"path": "big.txt", "content": "x" * (MAX_CONTENT_LENGTH + 1)}, ToolContext())


@pytest.mark.asyncio
async def test_write_file_backup_failure(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    f = tmp_path / "existing.txt"
    f.write_text("old content", encoding="utf-8")

    # Make write_text on backup path fail
    original_write_text = type(f).write_text

    def failing_write_text(self, *args, **kwargs):
        if str(self).endswith(".bak"):
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(type(f), "write_text", failing_write_text)

    result = await _dispatch(registry, "write_file", {"path": "existing.txt", "content": "new"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["written"] is True
    assert "backup" not in data


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_file_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "edit_file")
    result = handler({"path": "missing.txt", "old_text": "a", "new_text": "b"}, ToolContext())
    assert result["error"] == "File not found"


@pytest.mark.asyncio
async def test_edit_file_old_text_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    handler = _get_handler(registry, "edit_file")

    result = handler({"path": "test.txt", "old_text": "xyz", "new_text": "abc"}, ToolContext())
    assert result["matched"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_edit_file_old_text_not_unique(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello hello world", encoding="utf-8")
    handler = _get_handler(registry, "edit_file")

    result = handler({"path": "test.txt", "old_text": "hello", "new_text": "hi"}, ToolContext())
    assert "matches 2 times" in result["error"]
    assert result["matched"] is False


@pytest.mark.asyncio
async def test_edit_file_success(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")

    result = await _dispatch(registry, "edit_file", {"path": "test.txt", "old_text": "hello", "new_text": "hi"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["edited"] is True
    assert data["matched"] is True
    assert f.read_text(encoding="utf-8") == "hi world"


# ---------------------------------------------------------------------------
# append_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_file_content_too_long(tmp_path):
    registry = _make_registry(tmp_path)
    from metis.config import MAX_CONTENT_LENGTH
    handler = _get_handler(registry, "append_file")

    with pytest.raises(ValueError, match="maximum length"):
        handler({"path": "big.txt", "content": "x" * (MAX_CONTENT_LENGTH + 1)}, ToolContext())


@pytest.mark.asyncio
async def test_append_file_success(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello ", encoding="utf-8")

    result = await _dispatch(registry, "append_file", {"path": "test.txt", "content": "world"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["appended"] is True
    assert data["content_length"] == 5
    assert f.read_text(encoding="utf-8") == "hello world"


@pytest.mark.asyncio
async def test_append_file_creates_new(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "append_file", {"path": "new.txt", "content": "created"})
    assert result.status == "ok"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "created"


# ---------------------------------------------------------------------------
# diff_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diff_files_path_a_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "diff_files")
    result = handler({"path_a": "a.txt", "path_b": "b.txt"}, ToolContext())
    assert "File not found" in result["error"]


@pytest.mark.asyncio
async def test_diff_files_path_b_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    handler = _get_handler(registry, "diff_files")

    result = handler({"path_a": "a.txt", "path_b": "b.txt"}, ToolContext())
    assert "File not found" in result["error"]


@pytest.mark.asyncio
async def test_diff_files_max_diff_lines_truncation(tmp_path):
    registry = _make_registry(tmp_path)
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
    b.write_text("\n".join(f"other{i}" for i in range(100)), encoding="utf-8")

    result = await _dispatch(registry, "diff_files", {"path_a": "a.txt", "path_b": "b.txt", "max_diff_lines": 5})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["diff_count"] == 5
    assert data["truncated"] is True


@pytest.mark.asyncio
async def test_diff_files_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.txt").write_text("line1\nline2\nline3", encoding="utf-8")
    (tmp_path / "b.txt").write_text("line1\nchanged\nline3", encoding="utf-8")

    result = await _dispatch(registry, "diff_files", {"path_a": "a.txt", "path_b": "b.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["diff_count"] == 1
    assert data["differences"][0]["line"] == 2
    assert data["differences"][0]["a"] == "line2"
    assert data["differences"][0]["b"] == "changed"


# ---------------------------------------------------------------------------
# get_environment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_environment_workspace_entries(tmp_path):
    registry = _make_registry(tmp_path)
    # Create some files/dirs
    (tmp_path / "file1.txt").write_text("a", encoding="utf-8")
    (tmp_path / "file2.txt").write_text("b", encoding="utf-8")
    (tmp_path / ".hidden").write_text("c", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    result = await _dispatch(registry, "get_environment", {"path": "."})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert "python_version" in data
    assert "platform" in data
    assert "workspace_top_entries" in data
    # hidden files should be excluded
    entries = data["workspace_top_entries"]
    assert "file1.txt" in entries
    assert "file2.txt" in entries
    assert ".hidden" not in entries
    assert "subdir" in entries


@pytest.mark.asyncio
async def test_get_environment_pip_failure(monkeypatch, tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "get_environment")

    # Make subprocess.run fail for pip list
    import metis.tools.builtin as builtin_mod
    original_run = builtin_mod.subprocess.run

    def failing_run(*args, **kwargs):
        cmd = args[0] if args else []
        if "-m" in cmd and "pip" in cmd:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 15))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(builtin_mod.subprocess, "run", failing_run)

    result = handler({}, ToolContext())
    assert result.get("packages_count", 0) == 0


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_hash_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "compute_hash")
    # .env is in DENY_FILES and is a file, so it will trigger the read-denied check
    # after passing the is_file() check in the handler.
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_compute_hash_not_a_file(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "compute_hash")
    (tmp_path / "adir").mkdir()
    result = handler({"path": "adir"}, ToolContext())
    assert "Not a file" in result["error"]


@pytest.mark.asyncio
async def test_compute_hash_unsupported_algorithm(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "compute_hash")
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")
    result = handler({"path": "test.txt", "algorithm": "crc32"}, ToolContext())
    assert "Unsupported algorithm" in result["error"]


@pytest.mark.asyncio
async def test_compute_hash_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")

    result = await _dispatch(registry, "compute_hash", {"path": "test.txt", "algorithm": "sha256"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["algorithm"] == "sha256"
    assert len(data["hash"]) == 64
    assert data["file_size"] == 5


@pytest.mark.asyncio
async def test_compute_hash_md5_and_sha1(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "test.txt").write_text("hello", encoding="utf-8")

    for algo in ("md5", "sha1"):
        result = await _dispatch(registry, "compute_hash", {"path": "test.txt", "algorithm": algo})
        assert result.status == "ok"
        data = json.loads(result.content)
        assert data["algorithm"] == algo


# ---------------------------------------------------------------------------
# path_exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_path_exists_file(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "test.txt").write_text("a", encoding="utf-8")

    result = await _dispatch(registry, "path_exists", {"path": "test.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["exists"] is True
    assert data["is_file"] is True
    assert data["is_dir"] is False


@pytest.mark.asyncio
async def test_path_exists_dir(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "subdir").mkdir()

    result = await _dispatch(registry, "path_exists", {"path": "subdir"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["exists"] is True
    assert data["is_file"] is False
    assert data["is_dir"] is True


@pytest.mark.asyncio
async def test_path_exists_missing(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "path_exists", {"path": "missing.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["exists"] is False
    assert data["is_file"] is False
    assert data["is_dir"] is False


# ---------------------------------------------------------------------------
# read_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_files_empty_paths(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_files")
    result = handler({"paths": []}, ToolContext())
    assert "non-empty array" in result["error"]


@pytest.mark.asyncio
async def test_read_files_too_many_paths(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_files")
    result = handler({"paths": ["a"] * 21}, ToolContext())
    assert "Too many paths" in result["error"]


@pytest.mark.asyncio
async def test_read_files_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_files")
    result = handler({"paths": ["missing.txt"]}, ToolContext())
    assert result["results"]["missing.txt"]["error"] == "Not a file or not found"


@pytest.mark.asyncio
async def test_read_files_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_files")
    # Use .env which is in DENY_FILES
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    result = handler({"paths": [".env"]}, ToolContext())
    assert "Read denied" in result["results"][".env"]["error"]


@pytest.mark.asyncio
async def test_read_files_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.txt").write_text("content a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("content b", encoding="utf-8")

    result = await _dispatch(registry, "read_files", {"paths": ["a.txt", "b.txt"]})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["results"]["a.txt"]["content"] == "content a"
    assert data["results"]["b.txt"]["content"] == "content b"
    assert data["count"] == 2


# ---------------------------------------------------------------------------
# detect_file_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_file_type_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "detect_file_type")
    result = handler({"path": "missing.py"}, ToolContext())
    assert "Not a file" in result["error"]


@pytest.mark.asyncio
async def test_detect_file_type_python(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "script.py"
    f.write_text("# hello\nprint(1)\n\nprint(2)\n", encoding="utf-8")

    result = await _dispatch(registry, "detect_file_type", {"path": "script.py"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["language"] == "Python"
    assert data["extension"] == ".py"
    assert data["total_lines"] == 4
    assert data["non_empty_lines"] == 3
    assert data["blank_lines"] == 1


@pytest.mark.asyncio
async def test_detect_file_type_dockerfile(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "Dockerfile"
    f.write_text("FROM python:3.11\n", encoding="utf-8")

    result = await _dispatch(registry, "detect_file_type", {"path": "Dockerfile"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["language"] == "Dockerfile"
    assert data["extension"] == ""


@pytest.mark.asyncio
async def test_detect_file_type_makefile(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "Makefile"
    f.write_text("all:\n\techo ok\n", encoding="utf-8")

    result = await _dispatch(registry, "detect_file_type", {"path": "Makefile"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["language"] == "Makefile"


@pytest.mark.asyncio
async def test_detect_file_type_unknown(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "data.xyz"
    f.write_text("some data", encoding="utf-8")

    result = await _dispatch(registry, "detect_file_type", {"path": "data.xyz"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["language"] == "Unknown"


# ---------------------------------------------------------------------------
# store_memory / recall_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_memory_key_too_long(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "store_memory")
    result = handler({"key": "x" * 201, "value": "v"}, ToolContext())
    assert "Key too long" in result["error"]


@pytest.mark.asyncio
async def test_store_memory_value_too_long(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "store_memory")
    result = handler({"key": "k", "value": "x" * 10001}, ToolContext())
    assert "Value too long" in result["error"]


@pytest.mark.asyncio
async def test_store_and_recall_memory(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "store_memory", {"key": "mykey", "value": "myvalue"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["stored"] is True

    result = await _dispatch(registry, "recall_memory", {"key": "mykey"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["found"] is True
    assert data["value"] == "myvalue"


@pytest.mark.asyncio
async def test_recall_memory_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "recall_memory", {"key": "missing"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["found"] is False


@pytest.mark.asyncio
async def test_recall_memory_list_keys(tmp_path):
    registry = _make_registry(tmp_path)
    await _dispatch(registry, "store_memory", {"key": "k1", "value": "v1"})
    await _dispatch(registry, "store_memory", {"key": "k2", "value": "v2"})

    result = await _dispatch(registry, "recall_memory", {})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert set(data["keys"]) == {"k1", "k2"}
    assert data["count"] == 2


# ---------------------------------------------------------------------------
# rename_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_file_source_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "rename_file")
    result = handler({"old_path": "old.txt", "new_path": "new.txt"}, ToolContext())
    assert "Source not found" in result["error"]


@pytest.mark.asyncio
async def test_rename_file_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "old.txt").write_text("content", encoding="utf-8")

    result = await _dispatch(registry, "rename_file", {"old_path": "old.txt", "new_path": "subdir/new.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["renamed"] is True
    assert (tmp_path / "subdir" / "new.txt").exists()
    assert not (tmp_path / "old.txt").exists()


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_file_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "delete_file")
    result = handler({"path": "missing.txt"}, ToolContext())
    assert "Not found" in result["error"]


@pytest.mark.asyncio
async def test_delete_file_is_directory(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "adir").mkdir()
    handler = _get_handler(registry, "delete_file")
    result = handler({"path": "adir"}, ToolContext())
    assert "Cannot delete directories" in result["error"]


@pytest.mark.asyncio
async def test_delete_file_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "test.txt").write_text("content", encoding="utf-8")

    result = await _dispatch(registry, "delete_file", {"path": "test.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["deleted"] is True
    assert not (tmp_path / "test.txt").exists()


# ---------------------------------------------------------------------------
# copy_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_file_source_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "copy_file")
    result = handler({"source": "missing.txt", "destination": "dest.txt"}, ToolContext())
    assert "Source not found" in result["error"]


@pytest.mark.asyncio
async def test_copy_file_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")

    result = await _dispatch(registry, "copy_file", {"source": "src.txt", "destination": "dst/sub.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["copied"] is True
    assert data["size"] == 5
    assert (tmp_path / "dst" / "sub.txt").read_text(encoding="utf-8") == "hello"


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mkdir_new(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "mkdir", {"path": "newdir"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["created"] is True
    assert (tmp_path / "newdir").is_dir()


@pytest.mark.asyncio
async def test_mkdir_existing(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "existing").mkdir()
    result = await _dispatch(registry, "mkdir", {"path": "existing"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["created"] is False


@pytest.mark.asyncio
async def test_mkdir_nested(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "mkdir", {"path": "a/b/c"})
    assert result.status == "ok"
    assert (tmp_path / "a" / "b" / "c").is_dir()


# ---------------------------------------------------------------------------
# run_shell
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_shell_dangerous_command(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_shell")
    result = handler({"command": "rm -rf /"}, ToolContext())
    assert result["exit_code"] == -1
    assert "Blocked dangerous command" in result["stderr"]


@pytest.mark.asyncio
async def test_run_shell_not_allowed(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_shell")
    result = handler({"command": "rm file.txt"}, ToolContext())
    assert result["exit_code"] == -1
    assert "Blocked" in result["stderr"]


@pytest.mark.asyncio
async def test_run_shell_shlex_failure(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_shell")
    # A command with unclosed quote that makes shlex.split fail
    result = handler({"command": "echo 'unclosed"}, ToolContext())
    # shlex.split raises ValueError, falls back to str.split()
    # echo is allowed, so it should execute successfully
    assert result["exit_code"] == 0
    assert "unclosed" in result["stdout"]


@pytest.mark.asyncio
async def test_run_shell_success(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "run_shell", {"command": "echo hello"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["exit_code"] == 0
    assert "hello" in data["stdout"]


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_command_dangerous(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_command")
    result = handler({"command": "rm -rf /"}, ToolContext())
    assert result["exit_code"] == -1
    assert "Blocked dangerous command" in result["stderr"]


@pytest.mark.asyncio
async def test_run_command_not_allowed(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_command")
    result = handler({"command": ["rm", "-rf", "/"]}, ToolContext())
    assert result["exit_code"] == -1
    assert "Blocked" in result["stderr"]


@pytest.mark.asyncio
async def test_run_command_string_input(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_command")
    result = handler({"command": "echo hello world"}, ToolContext())
    assert result["exit_code"] == 0
    assert "hello world" in result["stdout"]


@pytest.mark.asyncio
async def test_run_command_array_input(tmp_path):
    registry = _make_registry(tmp_path)
    result = await _dispatch(registry, "run_command", {"command": ["echo", "hello"]})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["exit_code"] == 0
    assert "hello" in data["stdout"]


# ---------------------------------------------------------------------------
# run_test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_default_command(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_test")
    result = handler({}, ToolContext())
    assert result["test_framework"] == "pytest"
    # pytest returns exit code 5 when no tests are found, so passed is False
    assert result["passed"] is False
    assert result["exit_code"] == 5


@pytest.mark.asyncio
async def test_run_test_custom_command(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_test")
    result = handler({"command": ["python", "--version"]}, ToolContext())
    assert result["test_framework"] == "unknown"
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# get_file_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_info_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "get_file_info")
    result = handler({"path": "missing.txt"}, ToolContext())
    assert "File not found" in result["error"]


@pytest.mark.asyncio
async def test_get_file_info_success(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")

    result = await _dispatch(registry, "get_file_info", {"path": "test.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["name"] == "test.txt"
    assert data["extension"] == ".txt"
    assert data["size"] == 11
    assert data["is_file"] is True
    assert data["is_dir"] is False
    assert "modified" in data


# ---------------------------------------------------------------------------
# count_lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_lines_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "count_lines")
    result = handler({"path": "missing.txt"}, ToolContext())
    assert "Not a file" in result["error"]


@pytest.mark.asyncio
async def test_count_lines_success(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\n\nline3\n", encoding="utf-8")

    result = await _dispatch(registry, "count_lines", {"path": "test.txt"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["total_lines"] == 4
    assert data["non_empty_lines"] == 3
    assert data["blank_lines"] == 1


# ---------------------------------------------------------------------------
# read_file_range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_range_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_file_range")
    result = handler({"path": "missing.txt"}, ToolContext())
    assert "Not a file" in result["error"]


@pytest.mark.asyncio
async def test_read_file_range_success(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "test.txt"
    f.write_text("line0\nline1\nline2\nline3\nline4\n", encoding="utf-8")

    result = await _dispatch(registry, "read_file_range", {"path": "test.txt", "offset": 1, "limit": 2})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["offset"] == 1
    assert data["limit"] == 2
    assert data["total_lines"] == 5
    assert data["lines_returned"] == 2
    assert data["content"] == "line1\nline2"
    assert data["numbered"]["2"] == "line1"
    assert data["numbered"]["3"] == "line2"


# ---------------------------------------------------------------------------
# search_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_code_invalid_regex(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "search_code")
    result = handler({"pattern": "[invalid"}, ToolContext())
    assert "Invalid regex" in result["error"]


@pytest.mark.asyncio
async def test_search_code_files_with_matches(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def world(): pass\n", encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "def ", "output_mode": "files_with_matches"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 2
    files = {m["file"] for m in data["matches"]}
    assert "a.py" in files
    assert "b.py" in files


@pytest.mark.asyncio
async def test_search_code_content_mode(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "hello", "output_mode": "content"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 1
    assert data["matches"][0]["line"] == 1
    assert "hello" in data["matches"][0]["text"]


@pytest.mark.asyncio
async def test_search_code_case_insensitive(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.py").write_text("DEF hello(): pass\n", encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "def", "case_insensitive": True})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_search_code_max_results(tmp_path):
    registry = _make_registry(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text(f"def func{i}(): pass\n", encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "def ", "max_results": 3})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_search_code_skips_hidden(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / ".hidden.py").write_text("def secret(): pass\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("def public(): pass\n", encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "def "})
    assert result.status == "ok"
    data = json.loads(result.content)
    files = {m["file"] for m in data["matches"]}
    assert "visible.py" in files
    assert ".hidden.py" not in files


@pytest.mark.asyncio
async def test_search_code_skips_large_files(tmp_path):
    registry = _make_registry(tmp_path)
    f = tmp_path / "huge.py"
    f.write_text("x" * 2_000_000, encoding="utf-8")

    result = await _dispatch(registry, "search_code", {"pattern": "x"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 0


# ---------------------------------------------------------------------------
# find_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_files_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.py").write_text("b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("c", encoding="utf-8")

    result = await _dispatch(registry, "find_files", {"pattern": "*.py"})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 2
    names = {f["name"] for f in data["files"]}
    assert names == {"a.py", "b.py"}


@pytest.mark.asyncio
async def test_find_files_max_results(tmp_path):
    registry = _make_registry(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "find_files", {"pattern": "*.py", "max_results": 3})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_find_files_skips_hidden(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / ".hidden.py").write_text("x", encoding="utf-8")
    (tmp_path / "visible.py").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "find_files", {"pattern": "*.py"})
    assert result.status == "ok"
    data = json.loads(result.content)
    names = {f["name"] for f in data["files"]}
    assert "visible.py" in names
    assert ".hidden.py" not in names


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_directory_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "list_directory")
    result = handler({"path": "missing"}, ToolContext())
    assert "Not a directory" in result["error"]


@pytest.mark.asyncio
async def test_list_directory_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "file.txt").write_text("a", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    (tmp_path / ".hidden").write_text("b", encoding="utf-8")

    result = await _dispatch(registry, "list_directory", {"path": "."})
    assert result.status == "ok"
    data = json.loads(result.content)
    names = {e["name"] for e in data["entries"]}
    assert "file.txt" in names
    assert "subdir" in names
    assert ".hidden" not in names
    # Directories should come first
    types = [e["type"] for e in data["entries"]]
    assert types[0] == "directory"


@pytest.mark.asyncio
async def test_list_directory_show_hidden(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / ".hidden").write_text("b", encoding="utf-8")

    result = await _dispatch(registry, "list_directory", {"path": ".", "show_hidden": True})
    assert result.status == "ok"
    data = json.loads(result.content)
    names = {e["name"] for e in data["entries"]}
    assert ".hidden" in names


@pytest.mark.asyncio
async def test_list_directory_max_entries(tmp_path):
    registry = _make_registry(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "list_directory", {"path": ".", "max_entries": 3})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert data["count"] == 3


# ---------------------------------------------------------------------------
# tree_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tree_summary_not_found(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "tree_summary")
    result = handler({"path": "missing"}, ToolContext())
    assert "Not a directory" in result["error"]


@pytest.mark.asyncio
async def test_tree_summary_success(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    d = tmp_path / "subdir"
    d.mkdir()
    (d / "b.txt").write_text("b", encoding="utf-8")

    result = await _dispatch(registry, "tree_summary", {"path": "."})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert "a.txt" in data["tree"]
    assert "subdir/" in data["tree"]
    assert "b.txt" in data["tree"]
    assert data["total_files"] == 2
    assert data["total_dirs"] == 1


@pytest.mark.asyncio
async def test_tree_summary_max_depth(tmp_path):
    registry = _make_registry(tmp_path)
    d1 = tmp_path / "a"
    d1.mkdir()
    d2 = d1 / "b"
    d2.mkdir()
    d3 = d2 / "c"
    d3.mkdir()
    (d3 / "deep.txt").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "tree_summary", {"path": ".", "max_depth": 2})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert "a/" in data["tree"]
    assert "b/" in data["tree"]
    # c/ and deep.txt should not appear due to max_depth
    assert "deep.txt" not in data["tree"]


@pytest.mark.asyncio
async def test_tree_summary_max_entries(tmp_path):
    registry = _make_registry(tmp_path)
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "tree_summary", {"path": ".", "max_entries": 5})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert "..." in data["tree"]


@pytest.mark.asyncio
async def test_tree_summary_skips_hidden(tmp_path):
    registry = _make_registry(tmp_path)
    (tmp_path / ".hidden").write_text("x", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("x", encoding="utf-8")

    result = await _dispatch(registry, "tree_summary", {"path": "."})
    assert result.status == "ok"
    data = json.loads(result.content)
    assert "visible.txt" in data["tree"]
    assert ".hidden" not in data["tree"]


# ---------------------------------------------------------------------------
# Additional coverage for denied / OSError paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_write_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "write_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"path": ".env", "content": "x"}, ToolContext())


@pytest.mark.asyncio
async def test_edit_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "edit_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"path": ".env", "old_text": "s", "new_text": "x"}, ToolContext())


@pytest.mark.asyncio
async def test_append_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "append_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"path": ".env", "content": "x"}, ToolContext())


@pytest.mark.asyncio
async def test_diff_files_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "diff_files")
    (tmp_path / ".env").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path_a": ".env", "path_b": "b.txt"}, ToolContext())


@pytest.mark.asyncio
async def test_diff_files_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "diff_files")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    orig_read_text = type(tmp_path).read_text

    def failing_read_text(self, *args, **kwargs):
        if "a.txt" in str(self):
            raise OSError("read error")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "read_text", failing_read_text)

    result = handler({"path_a": "a.txt", "path_b": "b.txt"}, ToolContext())
    assert "read error" in result["error"]


@pytest.mark.asyncio
async def test_get_environment_workspace_truncation(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "get_environment")
    # Create more than 30 entries
    for i in range(35):
        (tmp_path / f"f{i:02d}.txt").write_text("x", encoding="utf-8")

    result = handler({"path": "."}, ToolContext())
    assert len(result["workspace_top_entries"]) == 30


@pytest.mark.asyncio
async def test_compute_hash_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "compute_hash")
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")

    def failing_open(*args, **kwargs):
        raise OSError("disk read error")

    monkeypatch.setattr("builtins.open", failing_open)

    result = handler({"path": "test.txt"}, ToolContext())
    assert "disk read error" in result["error"]


@pytest.mark.asyncio
async def test_read_files_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_files")
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")

    def failing_read_text(self, *args, **kwargs):
        raise OSError("cannot open")

    monkeypatch.setattr(type(tmp_path), "read_text", failing_read_text)

    result = handler({"paths": ["test.txt"]}, ToolContext())
    assert "cannot open" in result["results"]["test.txt"]["error"]


@pytest.mark.asyncio
async def test_detect_file_type_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "detect_file_type")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_detect_file_type_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "detect_file_type")
    f = tmp_path / "test.py"
    f.write_text("print(1)", encoding="utf-8")

    def failing_read_text(self, *args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(type(tmp_path), "read_text", failing_read_text)

    result = handler({"path": "test.py"}, ToolContext())
    # When read_text fails, lines becomes [] and the function still returns
    assert result["total_lines"] == 0


@pytest.mark.asyncio
async def test_rename_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "rename_file")
    (tmp_path / "old.txt").write_text("x", encoding="utf-8")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"old_path": "old.txt", "new_path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_delete_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "delete_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_copy_file_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "copy_file")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"source": ".env", "destination": "copy.txt"}, ToolContext())


@pytest.mark.asyncio
async def test_copy_file_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "copy_file")
    (tmp_path / "src.txt").write_text("x", encoding="utf-8")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"source": "src.txt", "destination": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_mkdir_write_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "mkdir")
    with pytest.raises(PermissionError, match="Write denied"):
        handler({"path": ".ssh/newdir"}, ToolContext())


@pytest.mark.asyncio
async def test_run_command_not_allowed_base(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "run_command")
    result = handler({"command": ["notallowed", "x"]}, ToolContext())
    assert result["exit_code"] == -1
    assert "Blocked" in result["stderr"]


@pytest.mark.asyncio
async def test_get_file_info_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "get_file_info")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_count_lines_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "count_lines")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_count_lines_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "count_lines")
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")

    def failing_read_text(self, *args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(type(tmp_path), "read_text", failing_read_text)

    result = handler({"path": "test.txt"}, ToolContext())
    assert "read failed" in result["error"]


@pytest.mark.asyncio
async def test_read_file_range_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_file_range")
    (tmp_path / ".env").write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".env"}, ToolContext())


@pytest.mark.asyncio
async def test_read_file_range_oserror(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_file_range")
    f = tmp_path / "test.txt"
    f.write_text("hello", encoding="utf-8")

    def failing_read_text(self, *args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(type(tmp_path), "read_text", failing_read_text)

    result = handler({"path": "test.txt"}, ToolContext())
    assert "read failed" in result["error"]


@pytest.mark.asyncio
async def test_search_code_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "search_code")
    (tmp_path / ".ssh").mkdir()
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"pattern": "test", "path": ".ssh"}, ToolContext())


@pytest.mark.asyncio
async def test_search_code_skips_permission_error(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "search_code")
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")

    def perm_error_read_text(self, *args, **kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr(type(tmp_path), "read_text", perm_error_read_text)

    result = handler({"pattern": "def", "path": "."}, ToolContext())
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_find_files_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "find_files")
    (tmp_path / ".ssh").mkdir()
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"pattern": "*", "path": ".ssh"}, ToolContext())


@pytest.mark.asyncio
async def test_list_directory_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "list_directory")
    (tmp_path / ".ssh").mkdir()
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".ssh"}, ToolContext())


@pytest.mark.asyncio
async def test_list_directory_permission_error_on_iterdir(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "list_directory")
    d = tmp_path / "locked"
    d.mkdir()

    def failing_iterdir(self):
        raise PermissionError("access denied")

    monkeypatch.setattr(type(tmp_path), "iterdir", failing_iterdir)

    result = handler({"path": "locked"}, ToolContext())
    assert "Permission denied" in result["error"]


@pytest.mark.asyncio
async def test_list_directory_oserror_on_stat(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "list_directory")
    d = tmp_path / "testdir"
    d.mkdir()
    (d / "good.txt").write_text("x", encoding="utf-8")
    (d / "bad.txt").write_text("y", encoding="utf-8")

    # The OSError on stat happens in the loop at line 619, not during sorting at line 610.
    # But sorted() calls is_dir() which also calls stat(). So we need to only fail
    # the stat call AFTER the sorted() succeeds. We do this by making stat fail
    # only on the second call (sorted uses stat once via is_dir, then the loop uses it).
    call_counts = {}

    orig_stat = type(tmp_path).stat

    def selective_failing_stat(self, **kwargs):
        key = str(self)
        call_counts[key] = call_counts.get(key, 0) + 1
        if "bad.txt" in str(self) and call_counts[key] > 1:
            raise OSError("stat failed")
        return orig_stat(self, **kwargs)

    monkeypatch.setattr(type(tmp_path), "stat", selective_failing_stat)

    result = handler({"path": "testdir"}, ToolContext())
    # The file with stat error should be skipped
    names = {e["name"] for e in result["entries"]}
    assert "good.txt" in names
    assert "bad.txt" not in names


@pytest.mark.asyncio
async def test_tree_summary_read_denied(tmp_path):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "tree_summary")
    (tmp_path / ".ssh").mkdir()
    with pytest.raises(PermissionError, match="Read denied"):
        handler({"path": ".ssh"}, ToolContext())


@pytest.mark.asyncio
async def test_tree_summary_permission_error_on_walk(tmp_path, monkeypatch):
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "tree_summary")
    d = tmp_path / "locked"
    d.mkdir()

    def failing_iterdir(self):
        raise PermissionError("access denied")

    monkeypatch.setattr(type(tmp_path), "iterdir", failing_iterdir)

    result = handler({"path": "locked"}, ToolContext())
    assert result["tree"] == ""
    assert result["total_files"] == 0
    assert result["total_dirs"] == 0


# ---------------------------------------------------------------------------
# Final edge-case coverage for remaining uncovered lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_code_skips_directories(tmp_path):
    """Line 546: rglob returns directories which should be skipped."""
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "search_code")
    # Create a subdirectory - rglob will return it as a path
    (tmp_path / "subdir").mkdir()
    (tmp_path / "a.py").write_text("def hello(): pass\n", encoding="utf-8")

    result = handler({"pattern": "def", "path": "."}, ToolContext())
    # Should only match the file, not the directory
    assert result["count"] == 1
    assert result["matches"][0]["file"] == "a.py"


@pytest.mark.asyncio
async def test_search_code_content_mode_max_results_break(tmp_path):
    """Line 567: break in content mode when max_results reached within a file."""
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "search_code")
    # Create a file with many matches
    lines = "\n".join(["hello world"] * 10)
    (tmp_path / "a.py").write_text(lines, encoding="utf-8")

    result = handler({"pattern": "hello", "output_mode": "content", "max_results": 3}, ToolContext())
    assert result["count"] == 3


@pytest.mark.asyncio
async def test_read_file_auto_decode_all_fail(tmp_path, monkeypatch):
    """Line 94: auto encoding fails for all supported encodings.

    This is nearly impossible in practice because latin-1 can decode any byte.
    We force it by making read_text raise UnicodeDecodeError for all encodings.
    """
    registry = _make_registry(tmp_path)
    handler = _get_handler(registry, "read_file")
    f = tmp_path / "test.bin"
    f.write_bytes(b"\x00\x01\x02")

    orig_read_text = type(tmp_path).read_text
    call_count = 0

    def always_failing_read_text(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise UnicodeDecodeError("test", b"", 0, 1, "forced failure")

    monkeypatch.setattr(type(tmp_path), "read_text", always_failing_read_text)

    result = handler({"path": "test.bin", "encoding": "auto"}, ToolContext())
    assert "Could not decode" in result["error"]
