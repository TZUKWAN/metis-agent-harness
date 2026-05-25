import json
from pathlib import Path

from metis.adapters.sophia import SophiaAdapter
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry


def test_sophia_adapter_registers_and_calls_inspection_tool():
    project_root = Path(r"D:\LATEXTEST\sophia-agent")
    registry = ToolRegistry()
    registration = SophiaAdapter(project_root).register(registry)

    result = ToolDispatcher(registry).dispatch(ToolCall(name="sophia_inspect_project", arguments={}))
    payload = json.loads(result.content)

    assert registration.tools == ["sophia_inspect_project"]
    assert payload["project"] == "sophia"
    assert payload["has_task_harness"] is True
    assert payload["python_files"] > 0
