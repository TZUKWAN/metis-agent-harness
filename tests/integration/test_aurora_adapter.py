import json
from pathlib import Path

from metis.adapters.aurora import AuroraAdapter
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry


def test_aurora_adapter_registers_and_calls_inspection_tool():
    project_root = Path(r"D:\LATEXTEST\aurora-agent")
    registry = ToolRegistry()
    registration = AuroraAdapter(project_root).register(registry)

    result = ToolDispatcher(registry).dispatch(ToolCall(name="aurora_inspect_project", arguments={}))
    payload = json.loads(result.content)

    assert registration.tools == ["aurora_inspect_project"]
    assert payload["project"] == "aurora"
    assert payload["has_agent"] is True
    assert payload["python_files"] > 0
