from pathlib import Path
import json
from dataclasses import fields

from metis.evals.runner import EvalTaskSpec, SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS
from metis.evals.suite_validation import BOOL_FIELDS, DICT_FIELDS, INT_FIELDS, LIST_FIELDS, PREDICATE_KEYS


def test_core_docs_exist():
    for name in [
        "architecture.md",
        "module-spec.md",
        "small-model-mode.md",
        "security-model.md",
        "extension-guide.md",
        "testing-strategy.md",
    ]:
        assert (Path("docs") / name).exists()


def test_eval_suite_schema_doc_covers_version_contract():
    path = Path("docs") / "evals" / "suite-schema.md"
    text = path.read_text(encoding="utf-8")

    for required in [
        "SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS",
        "schema_version",
        "Task Entry Forms",
        "EvalTaskSpec",
        "required_tool_arguments",
        "tool_schemas",
        "Compatibility Rules",
        "Migration Rules",
        "Release Gate Expectations",
    ]:
        assert required in text


def test_repair_plan_ci_recipe_covers_verified_phase_workflow():
    path = Path("docs") / "evals" / "repair-plan-ci-recipe.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")

    for required in [
        "metis eval compare",
        "metis eval diagnose",
        "metis eval repair-plan",
        "metis eval verify-repair-plan",
        "metis eval verify-eval-stubs",
        "metis eval verify-targeted-suite",
        "metis eval repair-execute",
        "metis eval verify-repair-preflight",
        "repair-execute-preflight.json",
        "repair-execute-preflight.md",
        "repair-execute-preflight-attestation.json",
        "METIS_ATTESTATION_SIGNING_KEY",
        "METIS_REQUIRE_ATTESTATION_SIGNATURE",
        "--record-attempt-status",
        "repair-execute-attempt.json",
        "updated-repair-plan",
        "--require-executable-phase",
        "--phase phase-1-stop-release-blockers",
        "repair-plan-attestation.json",
        "targeted-eval-stubs-attestation",
        "targeted-eval-suite-attestation",
        "phase-0-restore-artifact-trust",
        "phase-0b-repair-suite-hygiene",
        "never invoke a model on a blocked phase",
        "never invoke a model from an unattested repair plan",
    ]:
        assert required in text


def test_eval_suite_schema_v1_snapshot_matches_runner_contract():
    path = Path("docs") / "evals" / "suite-schema-v1.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    task_spec_properties = schema["$defs"]["eval_task_spec"]["properties"]

    assert schema["properties"]["schema_version"]["const"] == "1"
    assert schema["x-metis"]["supported_schema_versions"] == sorted(SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS)
    assert schema["x-metis"]["predicate_keys"] == sorted(PREDICATE_KEYS)
    assert schema["$defs"]["wrapped_task_entry"]["properties"]["tool_schemas"]["type"] == "object"
    assert set(task_spec_properties) == {field.name for field in fields(EvalTaskSpec)}
    for field_name in LIST_FIELDS:
        if field_name == "required_tool_arguments":
            assert task_spec_properties[field_name]["items"]["$ref"] == "#/$defs/required_tool_argument"
        elif field_name == "requirement_criteria":
            assert task_spec_properties[field_name]["items"]["type"] == "object"
        else:
            assert task_spec_properties[field_name]["$ref"] == "#/$defs/string_list"
    for field_name in BOOL_FIELDS:
        assert task_spec_properties[field_name]["type"] == "boolean"
    for field_name in INT_FIELDS:
        if field_name == "max_turns":
            assert task_spec_properties[field_name]["type"] == "integer"
            assert task_spec_properties[field_name]["minimum"] == 1
        else:
            assert task_spec_properties[field_name]["$ref"] == "#/$defs/non_negative_integer_or_null"
    for field_name in DICT_FIELDS:
        assert task_spec_properties[field_name]["type"] == "object"
