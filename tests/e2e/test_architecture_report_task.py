import json
import shutil
from pathlib import Path

import pytest

from metis.artifacts.store import ArtifactStore
from metis.evidence.ledger import EvidenceLedger
from metis.providers.fake import FakeProvider
from metis.quality.runner import QualityGateRunner
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_architecture_report_task_generates_real_report(tmp_path):
    fixture = Path(__file__).parents[1] / "fixtures" / "sample_project"
    workspace = tmp_path / "sample_project"
    shutil.copytree(fixture, workspace)
    report = "# Architecture Report\n\nPackage modules: calculator, formatter, pipeline. Tests cover calculator."
    read_paths = [
        "README.md",
        "sample_project/calculator.py",
        "sample_project/formatter.py",
        "sample_project/pipeline.py",
        "tests/test_calculator.py",
    ]
    responses = [{"tool_calls": [{"name": "read_file", "arguments": {"path": path}, "id": f"r{i}"}]} for i, path in enumerate(read_paths)]
    responses.append({"tool_calls": [{"name": "write_file", "arguments": {"path": "ARCHITECTURE.md", "content": report}, "id": "w1"}]})
    responses.append({"content": json.dumps({"status": "done", "summary": "report generated", "evidence_refs": [], "artifact_refs": [], "next_action": ""})})
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    registry = ToolRegistry()
    register_builtin_tools(registry, str(workspace))
    result = await AgentLoop(provider=FakeProvider(responses), registry=registry, state=state, workspace=str(workspace)).run(
        AgentRunRequest(session_id=session_id, messages=[{"role": "user", "content": "Create architecture report"}], allowed_tools=["read_file", "write_file"], max_turns=8)
    )

    artifact_store = ArtifactStore(state)
    artifact = artifact_store.register_artifact(session_id=session_id, path=workspace / "ARCHITECTURE.md", artifact_type="markdown")
    evidence = EvidenceLedger(state).record_claim(session_id=session_id, claim="Read fixture files", source_type="artifact", source_ref=artifact.id)
    quality = QualityGateRunner().run(["artifact_exists", "artifact_non_empty", "no_placeholder"], {"artifacts": [artifact], "evidence": [evidence], "tool_results": result.tool_results})

    assert result.status == "final"
    assert len([item for item in result.tool_results if item.tool_name == "read_file"]) == 5
    assert quality.passed is True
