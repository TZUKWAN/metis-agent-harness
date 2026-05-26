import json

from metis.adapters.sophia import SophiaAdapter
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry


def test_sophia_adapter_registers_and_calls_inspection_tool(tmp_path):
    project_root = tmp_path / "sophia-agent"
    project_root.mkdir()
    (project_root / "sophia").mkdir()
    (project_root / "sophia" / "task_harness.py").write_text("# sophia harness", encoding="utf-8")
    (project_root / "research").mkdir()
    (project_root / "research" / "study.py").write_text("# study", encoding="utf-8")

    registry = ToolRegistry()
    registration = SophiaAdapter(project_root).register(registry)

    result = ToolDispatcher(registry).dispatch(ToolCall(name="sophia_inspect_project", arguments={}))
    payload = json.loads(result.content)

    assert registration.tools == ["sophia_inspect_project"]
    assert payload["project"] == "sophia"
    assert payload["has_task_harness"] is True
    assert payload["python_files"] > 0
