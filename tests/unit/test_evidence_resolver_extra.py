"""Extra tests for metis/evidence/resolver.py to cover uncovered branches."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from metis.evidence.resolver import EvidenceResolution, EvidenceResolver


# --- source_type branches not yet covered ---

def test_resolve_user_input_evidence():
    evidence = {
        "source_type": "user_input",
        "source_ref": "user said X",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is True
    assert "user_input" in result.reason


def test_resolve_web_evidence():
    evidence = {
        "source_type": "web",
        "source_ref": "https://example.com",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is True
    assert "web" in result.reason


def test_resolve_api_evidence():
    evidence = {
        "source_type": "api",
        "source_ref": "api call",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is True
    assert "api" in result.reason


def test_resolve_git_evidence():
    evidence = {
        "source_type": "git",
        "source_ref": "abc123",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is True
    assert "git" in result.reason


def test_resolve_unsupported_source_type():
    evidence = {
        "source_type": "hallucination",
        "source_ref": "none",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is False
    assert "Unsupported" in result.reason


# --- artifact evidence branches ---

def test_resolve_artifact_without_artifact_store():
    evidence = {
        "source_type": "artifact",
        "source_ref": "art1",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=MagicMock(), artifact_store=None).resolve(evidence)
    assert result.passed is False
    assert "artifact_store" in result.reason


def test_resolve_artifact_source_ref_not_found_in_store():
    store = MagicMock()
    store.get_artifact.return_value = None
    evidence = {
        "source_type": "artifact",
        "source_ref": "nonexistent",
        "session_id": "s1",
    }
    result = EvidenceResolver(artifact_store=store).resolve(evidence)
    assert result.passed is False
    assert "not found" in result.reason


def test_resolve_artifact_wrong_session():
    artifact = MagicMock()
    artifact.session_id = "other_session"
    artifact.status = "created"
    store = MagicMock()
    store.get_artifact.return_value = artifact
    evidence = {
        "source_type": "artifact",
        "source_ref": "art1",
        "session_id": "s1",
    }
    result = EvidenceResolver(artifact_store=store).resolve(evidence)
    assert result.passed is False
    assert "another session" in result.reason


def test_resolve_artifact_bad_status():
    artifact = MagicMock()
    artifact.session_id = "s1"
    artifact.status = "corrupted"
    store = MagicMock()
    store.get_artifact.return_value = artifact
    evidence = {
        "source_type": "artifact",
        "source_ref": "art1",
        "session_id": "s1",
    }
    result = EvidenceResolver(artifact_store=store).resolve(evidence)
    assert result.passed is False
    assert "not accepted" in result.reason


def test_resolve_artifact_good():
    artifact = MagicMock()
    artifact.session_id = "s1"
    artifact.status = "validated"
    store = MagicMock()
    store.get_artifact.return_value = artifact
    evidence = {
        "source_type": "artifact",
        "source_ref": "art1",
        "session_id": "s1",
    }
    result = EvidenceResolver(artifact_store=store).resolve(evidence)
    assert result.passed is True
    assert "Artifact evidence resolved" in result.reason


# --- tool-backed evidence branches ---

def test_resolve_command_evidence_without_state():
    evidence = {
        "source_type": "command",
        "source_ref": "ls -la",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=None).resolve(evidence)
    assert result.passed is False
    assert "requires state store" in result.reason


def test_resolve_command_evidence_found_successful():
    state = MagicMock()
    state.list_tool_calls.return_value = [
        # First call has non-ok status, should be skipped (covers line 62)
        {"status": "error", "result": json.dumps({"command": "ls -la", "exit_code": 1})},
        # Second call is ok and matches
        {"status": "ok", "result": json.dumps({"command": "ls -la", "exit_code": 0})},
    ]
    evidence = {
        "source_type": "command",
        "source_ref": "ls -la",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=state).resolve(evidence)
    assert result.passed is True
    assert "command evidence resolved" in result.reason


def test_resolve_command_evidence_found_but_failed_exit_code():
    state = MagicMock()
    state.list_tool_calls.return_value = [
        {"status": "ok", "result": json.dumps({"command": "bad_cmd", "exit_code": 1})},
    ]
    evidence = {
        "source_type": "command",
        "source_ref": "bad_cmd",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=state).resolve(evidence)
    assert result.passed is False
    assert "did not succeed" in result.reason


def test_resolve_tool_output_evidence_found():
    state = MagicMock()
    state.list_tool_calls.return_value = [
        {"status": "ok", "result": json.dumps({"path": "/tmp/output.txt"})},
    ]
    evidence = {
        "source_type": "tool_output",
        "source_ref": "/tmp/output.txt",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=state).resolve(evidence)
    assert result.passed is True
    assert "Tool output evidence resolved" in result.reason


def test_resolve_tool_output_evidence_not_found():
    state = MagicMock()
    state.list_tool_calls.return_value = [
        {"status": "ok", "result": json.dumps({"path": "/other/file.txt"})},
    ]
    evidence = {
        "source_type": "tool_output",
        "source_ref": "/tmp/missing.txt",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=state).resolve(evidence)
    assert result.passed is False
    assert "not found" in result.reason


def test_resolve_command_evidence_not_found_in_calls():
    state = MagicMock()
    state.list_tool_calls.return_value = [
        {"status": "ok", "result": json.dumps({"command": "other_cmd", "exit_code": 0})},
    ]
    evidence = {
        "source_type": "command",
        "source_ref": "missing_cmd",
        "session_id": "s1",
    }
    result = EvidenceResolver(state=state).resolve(evidence)
    assert result.passed is False
    assert "not found" in result.reason


# --- file evidence ---

def test_resolve_file_evidence_exists(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("data", encoding="utf-8")
    evidence = {
        "source_type": "file",
        "source_ref": str(f),
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is True
    assert "File evidence resolved" in result.reason


def test_resolve_file_evidence_missing():
    evidence = {
        "source_type": "file",
        "source_ref": "/nonexistent/path/file.txt",
        "session_id": "s1",
    }
    result = EvidenceResolver().resolve(evidence)
    assert result.passed is False
    assert "not found" in result.reason


# --- _parse_result edge cases ---

def test_parse_result_invalid_json():
    result = EvidenceResolver._parse_result("not json{{{")
    assert result == {}


def test_parse_result_non_dict_json():
    result = EvidenceResolver._parse_result("[1, 2, 3]")
    assert result == {}


def test_parse_result_empty_string():
    result = EvidenceResolver._parse_result("")
    assert result == {}


def test_parse_result_valid_dict():
    result = EvidenceResolver._parse_result('{"key": "value"}')
    assert result == {"key": "value"}


# --- _command_text ---

def test_command_text_list():
    result = EvidenceResolver._command_text(["python", "-m", "pytest"])
    assert result == "python -m pytest"


def test_command_text_string():
    result = EvidenceResolver._command_text("python -m pytest")
    assert result == "python -m pytest"


# --- _field with object vs dict ---

def test_field_from_dict():
    assert EvidenceResolver._field({"source_type": "web"}, "source_type") == "web"


def test_field_from_object():
    obj = MagicMock()
    obj.source_type = "web"
    assert EvidenceResolver._field(obj, "source_type") == "web"


def test_field_missing_key_returns_empty_string():
    assert EvidenceResolver._field({}, "missing") == ""


# --- _metadata edge cases ---

def test_metadata_from_dict():
    assert EvidenceResolver._metadata({"metadata": {"key": 1}}) == {"key": 1}


def test_metadata_from_object():
    obj = MagicMock()
    obj.metadata = {"key": 2}
    assert EvidenceResolver._metadata(obj) == {"key": 2}


def test_metadata_non_dict_returns_empty():
    assert EvidenceResolver._metadata({"metadata": "not_a_dict"}) == {}


# --- EvidenceResolution dataclass ---

def test_evidence_resolution_defaults():
    r = EvidenceResolution(passed=True)
    assert r.reason == ""
    assert r.passed is True
