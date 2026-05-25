import json

from metis.evidence.extractor import ToolEvidenceExtractor
from metis.runtime.response import ToolResult


def test_evidence_extractor_detects_test_command_from_run_shell():
    result = ToolResult(
        "run_shell",
        json.dumps({"command": "python -m pytest -q", "exit_code": 0, "stdout": "3 passed"}),
    )

    evidence = ToolEvidenceExtractor().extract(result)

    assert evidence[0].source_type == "test"
    assert evidence[0].claim.startswith("Test command executed")
    assert evidence[0].metadata["exit_code"] == 0
    assert evidence[0].source_ref == "python -m pytest -q"


def test_evidence_extractor_detects_file_modification_from_dict():
    evidence = ToolEvidenceExtractor().extract({"tool_name": "write_file", "content": '{"path":"a.md"}', "status": "ok"})

    assert evidence[0].claim == "File modified: a.md"


def test_evidence_extractor_marks_run_test_as_test_evidence():
    result = ToolResult(
        "run_test",
        json.dumps(
            {
                "command": ["python", "-m", "pytest", "-q"],
                "command_text": "python -m pytest -q",
                "exit_code": 0,
                "stdout": "1 passed",
                "passed": True,
            }
        ),
    )

    evidence = ToolEvidenceExtractor().extract(result)

    assert evidence[0].source_type == "test"
    assert evidence[0].source_ref == "python -m pytest -q"
    assert evidence[0].metadata["passed"] is True
