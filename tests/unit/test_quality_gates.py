from metis.artifacts.store import ArtifactStore
from metis.evidence.ledger import EvidenceLedger
from metis.quality.runner import QualityGateRunner
from metis.runtime.response import ToolResult
from metis.state.sqlite_store import SQLiteStateStore


def test_quality_gates_pass_for_real_artifact_and_evidence(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    path = tmp_path / "report.md"
    path.write_text("Architecture report content", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(session_id=session_id, path=path, artifact_type="markdown")
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="report generated",
        source_type="artifact",
        source_ref=artifact.id,
    )

    result = QualityGateRunner().run(
        ["artifact_exists", "artifact_non_empty", "no_placeholder", "no_fake_completion"],
        {"artifacts": [artifact], "evidence": [evidence], "final_text": "已生成报告"},
    )

    assert result.passed is True


def test_quality_gate_fails_with_clear_message_for_missing_artifact():
    result = QualityGateRunner().run(["artifact_exists"], {"artifacts": []})

    assert result.passed is False
    assert "No artifacts" in result.failed_results[0].message
    assert result.failed_results[0].metadata == {
        "expected_artifacts": [],
        "missing_artifacts": [],
        "artifact_count": 0,
    }


def test_artifact_non_empty_gate_reports_empty_artifact_metadata(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(session_id=session_id, path=path, artifact_type="markdown")

    result = QualityGateRunner().run(["artifact_non_empty"], {"artifacts": [artifact]})

    assert result.passed is False
    assert result.failed_results[0].metadata == {
        "expected_artifacts": [artifact.path],
        "empty_artifacts": [artifact.path],
        "artifact_count": 1,
    }


def test_no_placeholder_gate_reports_placeholder_artifact_metadata(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    path = tmp_path / "draft.md"
    path.write_text("TODO: 待补充", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(session_id=session_id, path=path, artifact_type="markdown")

    result = QualityGateRunner().run(["no_placeholder"], {"artifacts": [artifact]})

    assert result.passed is False
    assert result.failed_results[0].metadata["expected_artifacts"] == [artifact.path]
    assert result.failed_results[0].metadata["placeholder_artifacts"] == [artifact.path]
    assert "Placeholder" in result.failed_results[0].metadata["placeholder_message"]


def test_requirements_covered_gate_reports_missing_requirements_metadata(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    path = tmp_path / "report.md"
    path.write_text("covered item", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(session_id=session_id, path=path, artifact_type="markdown")

    result = QualityGateRunner().run(
        ["requirements_covered"],
        {
            "artifacts": [artifact],
            "evidence": [],
            "final_text": "covered item",
            "requirements": ["covered", "missing"],
        },
    )

    assert result.passed is False
    assert result.failed_results[0].metadata == {
        "requirements": ["covered", "missing"],
        "requirement_criteria": [
            {"id": "", "text": "covered", "original_text": "covered", "index": 0},
            {"id": "", "text": "missing", "original_text": "missing", "index": 1},
        ],
        "missing_requirements": ["missing"],
        "missing_requirement_ids": [],
        "missing_artifact_paths": [],
        "missing_tools": [],
        "evidence_count": 0,
        "artifact_count": 1,
    }


def test_requirements_covered_gate_supports_structured_evidence_criteria(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="risk register",
        source_type="tool_output",
        source_ref="risk.md",
        strength="weak",
    )

    result = QualityGateRunner().run(
        ["requirements_covered"],
        {
            "evidence": [evidence],
            "final_text": "risk register",
            "requirement_criteria": [
                {
                    "id": "REQ-risk",
                    "text": "risk register",
                    "required_source_type": "tool_output",
                    "required_source_ref": "risk.md",
                    "min_strength": "strong",
                }
            ],
        },
    )

    assert result.passed is False
    assert result.failed_results[0].metadata["missing_requirements"] == ["risk register"]
    assert result.failed_results[0].metadata["missing_requirement_ids"] == ["REQ-risk"]
    assert result.failed_results[0].metadata["requirement_criteria"][0]["required_source_type"] == "tool_output"


def test_requirements_covered_gate_supports_artifact_and_tool_criteria(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    path = tmp_path / "outputs" / "report.md"
    path.parent.mkdir()
    path.write_text("deliver report", encoding="utf-8")
    artifact = ArtifactStore(state).register_artifact(session_id=session_id, path=path, artifact_type="markdown")

    result = QualityGateRunner().run(
        ["requirements_covered"],
        {
            "artifacts": [artifact],
            "tool_results": [ToolResult("read_file", "ok")],
            "final_text": "deliver report",
            "requirement_criteria": [
                {
                    "id": "REQ-deliver",
                    "text": "deliver report",
                    "required_artifact_path": "outputs/report.md",
                    "required_tool": "write_file",
                }
            ],
        },
    )

    assert result.passed is False
    metadata = result.failed_results[0].metadata
    assert metadata["missing_requirements"] == ["deliver report"]
    assert metadata["missing_requirement_ids"] == ["REQ-deliver"]
    assert metadata["missing_artifact_paths"] == []
    assert metadata["missing_tools"] == ["write_file"]

    passing = QualityGateRunner().run(
        ["requirements_covered"],
        {
            "artifacts": [artifact],
            "tool_results": [ToolResult("write_file", "ok")],
            "final_text": "deliver report",
            "requirement_criteria": [
                {
                    "id": "REQ-deliver",
                    "text": "deliver report",
                    "required_artifact_path": "outputs/report.md",
                    "required_tool": "write_file",
                }
            ],
        },
    )

    assert passing.passed is True


def test_requirements_covered_gate_supports_tool_only_criteria():
    result = QualityGateRunner().run(
        ["requirements_covered"],
        {
            "final_text": "",
            "requirement_criteria": [{"id": "REQ-tool", "required_tool": "write_file"}],
            "tool_results": [ToolResult("write_file", "ok")],
        },
    )

    assert result.passed is True
