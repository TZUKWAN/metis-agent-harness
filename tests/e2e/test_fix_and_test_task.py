import json
import shutil
from pathlib import Path

import pytest

from metis.providers.fake import FakeProvider
from metis.quality.runner import QualityGateRunner
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_fix_and_test_task_records_test_command_and_real_file_change(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_project_broken"
    workspace = tmp_path / "broken"
    shutil.copytree(fixture, workspace)
    fixed = "def add(a: int, b: int) -> int:\n    return a + b\n"
    responses = [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "sample_project/calculator.py"}, "id": "r1"}]},
        {"tool_calls": [{"name": "write_file", "arguments": {"path": "sample_project/calculator.py", "content": fixed}, "id": "w1"}]},
        {"tool_calls": [{"name": "run_shell", "arguments": {"command": "python -m pytest -q", "timeout": 30}, "id": "t1"}]},
        {"content": json.dumps({"status": "done", "summary": "tests passed", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    registry = ToolRegistry()
    register_builtin_tools(registry, str(workspace))

    result = await AgentLoop(provider=FakeProvider(responses), registry=registry, state=state, workspace=str(workspace)).run(
        AgentRunRequest(session_id=session_id, messages=[{"role": "user", "content": "Fix failing test"}], allowed_tools=["read_file", "write_file", "run_shell"], max_turns=6)
    )
    quality = QualityGateRunner().run(["no_fake_completion"], {"final_text": "The bug has been fixed and all tests have been tested", "tool_results": result.tool_results})

    assert "return a + b" in (workspace / "sample_project" / "calculator.py").read_text(encoding="utf-8")
    assert any(item.tool_name == "run_shell" for item in result.tool_results)
    assert quality.passed is True
