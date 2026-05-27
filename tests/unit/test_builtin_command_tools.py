import json

import pytest

from metis.runtime.response import ToolCall
from metis.tools.builtin import register_builtin_tools
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


@pytest.mark.asyncio
async def test_run_command_executes_without_shell(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    dispatcher = ToolDispatcher(registry)

    result = await dispatcher.dispatch(
        ToolCall("run_command", {"command": ["python", "-c", "print('ok')"]}, id="c1"),
        ToolContext(),
    )

    payload = json.loads(result.content)
    assert result.status == "ok"
    assert payload["exit_code"] == 0
    assert payload["stdout"].strip() == "ok"
    assert result.metadata["command"] == ["python", "-c", "print('ok')"]


@pytest.mark.asyncio
async def test_run_test_returns_structured_test_metadata(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    dispatcher = ToolDispatcher(registry)

    result = await dispatcher.dispatch(
        ToolCall("run_test", {"command": ["python", "-m", "pytest", "-q"]}, id="t1"),
        ToolContext(),
    )

    payload = json.loads(result.content)
    assert result.status == "ok"
    assert payload["passed"] is True
    assert payload["test_framework"] == "pytest"
    assert result.metadata["passed"] is True
