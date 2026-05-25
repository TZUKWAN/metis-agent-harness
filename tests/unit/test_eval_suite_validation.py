import hashlib
import json
from pathlib import Path

from metis.evals.suite_validation import (
    eval_suite_validation_to_markdown,
    validate_eval_suite,
    write_eval_suite_validation,
)


def test_validate_eval_suite_accepts_valid_materialized_suite(tmp_path):
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "targeted-eval-suite.json").write_text(
        json.dumps(
            {
                "suite": "targeted-repair-regression",
                "schema_version": "1",
                "tasks": [
                    {
                        "task_id": "targeted-repair-001",
                        "task_spec": {
                            "id": "targeted-repair-001",
                            "prompt": "Recover from schema failure.",
                            "allowed_tools": ["write_file"],
                            "max_turns": 4,
                            "required_tool_arguments": [
                                {"tool": "write_file", "arguments": {"path": "outputs/report.md"}}
                            ],
                            "max_schema_violations": 0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_dir)
    markdown = eval_suite_validation_to_markdown(report)

    assert report["valid"] is True
    assert report["error_count"] == 0
    assert report["task_count"] == 1
    assert report["schema_version"] == "1"
    assert report["supported_schema_versions"] == ["1"]
    assert report["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert report["suite_schema_path"].endswith("docs\\evals\\suite-schema-v1.json") or report["suite_schema_path"].endswith("docs/evals/suite-schema-v1.json")
    assert report["suite_schema_sha256"] == hashlib.sha256(
        (Path("docs") / "evals" / "suite-schema-v1.json").read_bytes()
    ).hexdigest()
    assert "Valid: True" in markdown
    assert "Supported schema versions: 1" in markdown
    assert "Suite schema id: https://metis.local/schemas/evals/suite-schema-v1.json" in markdown
    assert "Suite schema sha256:" in markdown


def test_validate_eval_suite_rejects_unsupported_schema_version(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "future-suite",
                "schema_version": "2",
                "tasks": [{"id": "future", "prompt": "Run."}],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    assert report["schema_version"] == "2"
    assert report["supported_schema_versions"] == ["1"]
    assert {
        "path": "schema_version",
        "code": "unsupported",
        "message": "Unsupported schema_version: 2. Supported versions: 1.",
    } in report["errors"]


def test_validate_eval_suite_reports_missing_prompt_duplicate_ids_and_bad_types(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "bad-suite",
                "schema_version": 1,
                "tasks": [
                    {
                        "id": "dup",
                        "prompt": "Run.",
                        "allowed_tools": "read_file",
                        "max_turns": 0,
                        "required_tool_arguments": [{"tool": 7, "arguments": []}],
                        "unknown": True,
                    },
                    {"id": "dup"},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    assert {issue["path"] for issue in report["errors"]} >= {
        "schema_version",
        "tasks[0].allowed_tools",
        "tasks[0].max_turns",
        "tasks[0].required_tool_arguments[0].tool",
        "tasks[0].required_tool_arguments[0].arguments",
        "tasks[1].id",
        "tasks[1].prompt",
    }
    assert report["warnings"] == [
        {
            "path": "tasks[0].unknown",
            "code": "unknown_field",
            "message": "Unknown EvalTaskSpec field will be ignored.",
        }
    ]


def test_validate_eval_suite_checks_tool_and_quality_gate_registries(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "registry-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "registry",
                        "prompt": "Run.",
                        "allowed_tools": ["read_file", "missing_tool"],
                        "required_tools": ["write_file"],
                        "forbidden_tools": ["ghost_tool"],
                        "required_tool_order": ["read_file", "unknown_order_tool"],
                        "required_tool_arguments": [
                            {"tool": "missing_argument_tool", "arguments": {"path": "x"}},
                        ],
                        "quality_gates": ["artifact_exists", "unknown_gate"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        available_tools={"read_file", "write_file"},
        available_quality_gates={"artifact_exists"},
    )

    assert report["valid"] is False
    issues = {(issue["path"], issue["code"]) for issue in report["errors"]}
    assert ("tasks[0].allowed_tools[1]", "unknown_tool") in issues
    assert ("tasks[0].forbidden_tools[0]", "unknown_tool") in issues
    assert ("tasks[0].required_tool_order[1]", "unknown_tool") in issues
    assert ("tasks[0].required_tool_arguments[0].tool", "unknown_tool") in issues
    assert ("tasks[0].quality_gates[1]", "unknown_quality_gate") in issues


def test_validate_eval_suite_checks_requirement_criteria_artifact_and_tool_fields(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "criteria-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "criteria",
                        "prompt": "Run.",
                        "requirement_criteria": [
                            {"id": "REQ-artifact", "required_artifact_path": "outputs/report.md"},
                            {"id": "REQ-tool", "required_tool": "missing_tool"},
                            {"id": "REQ-empty"},
                            {"id": "REQ-bad", "artifact_path": 7},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path, available_tools={"write_file"})

    assert report["valid"] is False
    issues = {(issue["path"], issue["code"]) for issue in report["errors"]}
    assert ("tasks[0].requirement_criteria[1].required_tool", "unknown_tool") in issues
    assert ("tasks[0].requirement_criteria[2]", "empty_requirement_criterion") in issues
    assert ("tasks[0].requirement_criteria[3].artifact_path", "invalid_type") in issues


def test_validate_eval_suite_rejects_non_portable_artifact_paths(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "artifact-path-policy",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "artifact-path-policy",
                        "prompt": "Run.",
                        "expected_artifacts": ["outputs/report.md", "../escape.md", "C:\\tmp\\report.md"],
                        "requirement_criteria": [
                            {"id": "REQ-abs", "required_artifact_path": "/tmp/report.md"},
                            {"id": "REQ-parent", "artifact_path": "outputs/../report.md"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    issues = {(issue["path"], issue["code"]) for issue in report["errors"]}
    assert ("tasks[0].expected_artifacts[1]", "invalid_artifact_path") in issues
    assert ("tasks[0].expected_artifacts[2]", "invalid_artifact_path") in issues
    assert ("tasks[0].requirement_criteria[0].required_artifact_path", "invalid_artifact_path") in issues
    assert ("tasks[0].requirement_criteria[1].artifact_path", "invalid_artifact_path") in issues


def test_validate_eval_suite_checks_required_tool_arguments_against_tool_schema(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "schema-ok",
                        "prompt": "Run.",
                        "required_tool_arguments": [
                            {
                                "tool": "read_file",
                                "arguments": {"path": {"contains": "README"}, "encoding": {"equals": "utf-8"}},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={
            "read_file": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "encoding": {"type": "string"}},
                "required": ["path"],
            }
        },
    )

    assert report["valid"] is True


def test_validate_eval_suite_uses_suite_local_tool_schemas(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "task_id": "custom-ok",
                        "tool_schemas": {
                            "crm_update": {
                                "type": "object",
                                "properties": {
                                    "customer_id": {"type": "integer"},
                                    "status": {"type": "string", "enum": ["qualified", "nurture"]},
                                },
                            }
                        },
                        "task_spec": {
                            "id": "custom-ok",
                            "prompt": "Run.",
                            "allowed_tools": ["crm_update"],
                            "required_tool_arguments": [
                                {
                                    "tool": "crm_update",
                                    "arguments": {"customer_id": 1000, "status": {"contains": "qualified"}},
                                }
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is True


def test_validate_eval_suite_rejects_suite_local_tool_schema_argument_mismatch(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "task_id": "custom-bad",
                        "tool_schemas": {
                            "crm_update": {
                                "type": "object",
                                "properties": {"customer_id": {"type": "integer"}},
                            }
                        },
                        "task_spec": {
                            "id": "custom-bad",
                            "prompt": "Run.",
                            "required_tool_arguments": [
                                {"tool": "crm_update", "arguments": {"customer_id": "not-an-int"}}
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    assert ("tasks[0].task_spec.required_tool_arguments[0].arguments.customer_id", "tool_argument_schema_mismatch") in {
        (issue["path"], issue["code"]) for issue in report["errors"]
    }


def test_validate_eval_suite_explicit_tool_schemas_override_suite_local_tool_schemas(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "task_id": "custom-override",
                        "tool_schemas": {
                            "crm_update": {
                                "type": "object",
                                "properties": {"customer_id": {"type": "integer"}},
                            }
                        },
                        "task_spec": {
                            "id": "custom-override",
                            "prompt": "Run.",
                            "required_tool_arguments": [
                                {"tool": "crm_update", "arguments": {"customer_id": "string-id"}}
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={"crm_update": {"type": "object", "properties": {"customer_id": {"type": "string"}}}},
    )

    assert report["valid"] is True


def test_validate_eval_suite_rejects_unknown_required_tool_argument_name(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "schema-bad",
                        "prompt": "Run.",
                        "required_tool_arguments": [{"tool": "read_file", "arguments": {"url": "README.md"}}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={"read_file": {"type": "object", "properties": {"path": {"type": "string"}}}},
    )

    assert report["valid"] is False
    assert {
        "path": "tasks[0].required_tool_arguments[0].arguments.url",
        "code": "unknown_tool_argument",
        "message": "Tool schema has no argument named 'url'.",
    } in report["errors"]


def test_validate_eval_suite_rejects_required_tool_argument_literal_type_mismatch(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "schema-bad-type",
                        "prompt": "Run.",
                        "required_tool_arguments": [{"tool": "run_command", "arguments": {"timeout": "fast"}}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={"run_command": {"type": "object", "properties": {"timeout": {"type": "integer"}}}},
    )

    assert report["valid"] is False
    assert ("tasks[0].required_tool_arguments[0].arguments.timeout", "tool_argument_schema_mismatch") in {
        (issue["path"], issue["code"]) for issue in report["errors"]
    }


def test_validate_eval_suite_rejects_text_predicate_for_numeric_tool_argument(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "schema-bad-predicate",
                        "prompt": "Run.",
                        "required_tool_arguments": [{"tool": "run_command", "arguments": {"timeout": {"contains": "3"}}}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={"run_command": {"type": "object", "properties": {"timeout": {"type": "integer"}}}},
    )

    assert report["valid"] is False
    assert ("tasks[0].required_tool_arguments[0].arguments.timeout.contains", "tool_argument_predicate_type_mismatch") in {
        (issue["path"], issue["code"]) for issue in report["errors"]
    }


def test_validate_eval_suite_rejects_bad_in_predicate_candidate_type(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "schema-suite",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "schema-bad-in",
                        "prompt": "Run.",
                        "required_tool_arguments": [
                            {"tool": "run_command", "arguments": {"timeout": {"in": [30, "fast"]}}}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(
        suite_path,
        tool_schemas={"run_command": {"type": "object", "properties": {"timeout": {"type": "integer"}}}},
    )

    assert report["valid"] is False
    assert ("tasks[0].required_tool_arguments[0].arguments.timeout.in[1]", "tool_argument_schema_mismatch") in {
        (issue["path"], issue["code"]) for issue in report["errors"]
    }


def test_validate_eval_suite_checks_list_items_are_strings(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "bad-list",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "bad-list",
                        "prompt": "Run.",
                        "allowed_tools": ["read_file", 42],
                        "quality_gates": [None],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    assert {"path": "tasks[0].allowed_tools[1]", "code": "invalid_type", "message": "list item must be a non-empty string."} in report["errors"]
    assert {"path": "tasks[0].quality_gates[0]", "code": "invalid_type", "message": "list item must be a non-empty string."} in report["errors"]


def test_validate_eval_suite_rejects_empty_tasks(tmp_path):
    suite_path = tmp_path / "empty.json"
    suite_path.write_text('{"suite": "empty", "tasks": []}', encoding="utf-8")

    report = validate_eval_suite(suite_path)

    assert report["valid"] is False
    assert report["errors"][0]["path"] == "tasks"
    assert report["errors"][0]["code"] == "empty"


def test_validate_eval_suite_accepts_utf8_bom_json(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        '\ufeff{"suite": "bom-suite", "schema_version": "1", "tasks": [{"id": "ok", "prompt": "Run."}]}',
        encoding="utf-8",
    )

    report = validate_eval_suite(suite_path)

    assert report["valid"] is True
    assert report["suite"] == "bom-suite"


def test_write_eval_suite_validation_outputs_json_and_markdown(tmp_path):
    report = {
        "path": "suite.json",
        "suite": "suite",
        "schema_version": "1",
        "task_count": 0,
        "valid": True,
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "warnings": [],
    }

    output_dir = write_eval_suite_validation(report, tmp_path / "validation")

    assert (output_dir / "suite-validation.json").exists()
    assert (output_dir / "suite-validation.md").exists()
