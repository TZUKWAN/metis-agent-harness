import json

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
async def test_small_model_report_task_reads_files_writes_artifact_and_passes_quality(tmp_path):
    workspace = tmp_path / "fixture_project"
    workspace.mkdir()
    files = {
        "README.md": "# Fixture\nA small project.",
        "app.py": "def main():\n    return 'ok'\n",
        "config.toml": "[app]\nname='fixture'\n",
        "tests.md": "Run pytest for validation.",
        "notes.md": "Architecture notes for the fixture.",
    }
    for path, content in files.items():
        (workspace / path).write_text(content, encoding="utf-8")

    report = (
        "# Architecture Report\n\n"
        "The fixture contains an app module, config, notes, tests, and README. "
        "The harness read all required project files and produced this report."
    )
    responses = []
    for index, path in enumerate(files, start=1):
        responses.append({"tool_calls": [{"name": "read_file", "arguments": {"path": path}, "id": f"read{index}"}]})
    responses.append(
        {
            "tool_calls": [
                {"name": "write_file", "arguments": {"path": "architecture_report.md", "content": report}, "id": "write1"}
            ]
        }
    )
    responses.append(
        {
            "content": json.dumps(
                {
                    "status": "done",
                    "summary": "Report generated after reading five files.",
                    "evidence_refs": [],
                    "artifact_refs": [],
                    "next_action": "",
                },
                ensure_ascii=False,
            )
        }
    )

    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("small-e2e")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, state=state, workspace=str(workspace), profile="small")

    result = await loop.run(
        AgentRunRequest(
            session_id=session_id,
            messages=[{"role": "user", "content": "Read the project and create an architecture report."}],
            allowed_tools=["read_file", "write_file"],
            max_turns=8,
        )
    )

    artifact_store = ArtifactStore(state)
    artifact = artifact_store.register_artifact(
        session_id=session_id,
        path=workspace / "architecture_report.md",
        artifact_type="markdown",
    )
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="Read five source files and wrote architecture_report.md",
        source_type="artifact",
        source_ref=artifact.id,
    )
    quality = QualityGateRunner().run(
        ["artifact_exists", "artifact_non_empty", "no_placeholder", "no_fake_completion"],
        {
            "artifacts": [artifact],
            "evidence": [evidence],
            "tool_results": result.tool_results,
            "final_text": "architecture_report.md has been generated",
        },
    )

    read_results = [item for item in result.tool_results if item.tool_name == "read_file"]
    assert result.status == "final"
    assert len(read_results) >= 5
    assert (workspace / "architecture_report.md").read_text(encoding="utf-8") == report
    assert artifact_store.get_artifact(artifact.id) == artifact
    assert quality.passed is True
