import pytest

from metis.security.paths import is_write_denied, resolve_workspace_path
from metis.tools.builtin import register_builtin_tools
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry


def test_resolve_workspace_path_blocks_escape(tmp_path):
    with pytest.raises(PermissionError):
        resolve_workspace_path(tmp_path, "..\\outside.txt")


def test_sensitive_path_is_write_denied(tmp_path):
    assert is_write_denied(tmp_path / ".ssh" / "config") is True
    assert is_write_denied(tmp_path / ".env") is True


def test_builtin_write_file_rejects_sensitive_path(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    result = ToolDispatcher(registry).dispatch(
        ToolCall(name="write_file", arguments={"path": ".env", "content": "SECRET=1"}, id="c1")
    )

    assert result.status == "error"
    assert "Write denied" in result.error
