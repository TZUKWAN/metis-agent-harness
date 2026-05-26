import json

from metis.adapters.aurora import AuroraAdapter
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry


def test_aurora_adapter_registers_and_calls_inspection_tool(tmp_path):
    project_root = tmp_path / "aurora-agent"
    project_root.mkdir()
    (project_root / "aurora").mkdir()
    (project_root / "aurora" / "agent.py").write_text("# aurora agent", encoding="utf-8")
    (project_root / "tools").mkdir()
    (project_root / "tools" / "helper.py").write_text("# helper", encoding="utf-8")

    registry = ToolRegistry()
    registration = AuroraAdapter(project_root).register(registry)

    result = ToolDispatcher(registry).dispatch(ToolCall(name="aurora_inspect_project", arguments={}))
    payload = json.loads(result.content)

    assert registration.tools == ["aurora_inspect_project"]
    assert payload["project"] == "aurora"
    assert payload["has_agent"] is True
    assert payload["python_files"] > 0
