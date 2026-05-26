"""Unit tests for edit_file tool."""

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def test_edit_file_basic(tmp_path):
    (tmp_path / "code.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    tool = registry.get("edit_file")
    result = tool.handler(
        {"path": "code.py", "old_text": "pass", "new_text": "return 'hello'"},
        ToolContext(session_id="test", workspace=".", allowed_tools=None),
    )
    assert result["edited"] is True
    assert (tmp_path / "code.py").read_text(encoding="utf-8") == "def hello():\n    return 'hello'\n"


def test_edit_file_not_found(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    tool = registry.get("edit_file")
    result = tool.handler(
        {"path": "missing.py", "old_text": "x", "new_text": "y"},
        ToolContext(session_id="test", workspace=".", allowed_tools=None),
    )
    assert "error" in result
    assert "not found" in result["error"]


def test_edit_file_old_text_not_found(tmp_path):
    (tmp_path / "code.py").write_text("print('hi')\n", encoding="utf-8")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    tool = registry.get("edit_file")
    result = tool.handler(
        {"path": "code.py", "old_text": "nonexistent", "new_text": "y"},
        ToolContext(session_id="test", workspace=".", allowed_tools=None),
    )
    assert result["matched"] is False
    assert (tmp_path / "code.py").read_text(encoding="utf-8") == "print('hi')\n"


def test_edit_file_ambiguous_match(tmp_path):
    (tmp_path / "code.py").write_text("x = 1\nx = 2\n", encoding="utf-8")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    tool = registry.get("edit_file")
    result = tool.handler(
        {"path": "code.py", "old_text": "x = ", "new_text": "y = "},
        ToolContext(session_id="test", workspace=".", allowed_tools=None),
    )
    assert result["matched"] is False
    assert "matches 2 times" in result["error"]
