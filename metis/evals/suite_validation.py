"""Validation helpers for loadable eval suite JSON."""

from __future__ import annotations

import json
import hashlib
from dataclasses import fields
from pathlib import Path
from typing import Any

from metis.evals.runner import EvalTaskSpec
from metis.evals.runner import SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS
from metis.tools.schema_validator import ToolArgumentSchemaValidator


LIST_FIELDS = {
    "allowed_tools",
    "expected_artifacts",
    "required_evidence_sources",
    "requirements",
    "requirement_criteria",
    "quality_gates",
    "required_tools",
    "forbidden_tools",
    "required_tool_order",
    "required_tool_arguments",
    "required_failure_shape_keys",
    "forbidden_failure_shape_keys",
}
STRING_LIST_FIELDS = LIST_FIELDS - {"required_tool_arguments", "requirement_criteria"}
DICT_FIELDS = {"artifact_verification", "max_failure_shape_key_counts"}
BOOL_FIELDS = {
    "requires_model_execution",
    "require_verified_final",
    "allow_recovered_schema_failures",
    "allow_recovered_tool_failures",
}
INT_FIELDS = {
    "max_turns",
    "max_duplicate_tool_calls",
    "max_invalid_tool_calls",
    "max_policy_blocks",
    "max_evidence_resolution_failures",
    "max_schema_violations",
    "min_schema_repair_successes",
    "max_schema_repair_failures",
    "min_schema_repair_hint_successes",
    "max_schema_repair_hint_failures",
    "min_tool_repair_successes",
    "max_tool_repair_failures",
    "max_retry_budget_exhaustions",
    "max_pre_dispatch_blocks",
}
PREDICATE_KEYS = {"equals", "contains", "startswith", "endswith", "in"}
SUITE_SCHEMA_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "docs" / "evals" / "suite-schema-v1.json"


def validate_eval_suite(
    path: str | Path,
    *,
    available_tools: set[str] | list[str] | None = None,
    available_quality_gates: set[str] | list[str] | None = None,
    tool_schemas: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    tool_names = set(available_tools) if available_tools is not None else set(tool_schemas) if tool_schemas is not None else None
    quality_gate_names = set(available_quality_gates) if available_quality_gates is not None else None
    try:
        payload = _load_eval_suite_payload(path)
    except Exception as exc:
        return _validation_report(
            path=path,
            payload={},
            errors=[_issue("suite", "load_failed", str(exc))],
            warnings=[],
        )
    _validate_top_level(payload, errors, warnings)
    merged_tool_schemas = _merged_tool_schemas(payload, tool_schemas)
    if available_tools is None and merged_tool_schemas:
        tool_names = set(merged_tool_schemas)
    tasks = payload.get("tasks", [])
    if isinstance(tasks, list):
        seen_ids: set[str] = set()
        for index, item in enumerate(tasks):
            task_spec = _task_spec_payload(item, index, errors)
            if task_spec is None:
                continue
            task_path = f"tasks[{index}].task_spec" if isinstance(item, dict) and "task_spec" in item else f"tasks[{index}]"
            _validate_task_spec(
                task_spec,
                task_path,
                errors,
                warnings,
                seen_ids,
                available_tools=tool_names,
                available_quality_gates=quality_gate_names,
                tool_schemas=merged_tool_schemas,
            )
    return _validation_report(path=path, payload=payload, errors=errors, warnings=warnings)


def eval_suite_validation_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Suite Validation",
        "",
        f"Path: {report.get('path', '')}",
        f"Suite: {report.get('suite', '')}",
        f"Schema version: {report.get('schema_version', '')}",
        f"Supported schema versions: {', '.join(report.get('supported_schema_versions', []))}",
        f"Suite schema id: {report.get('suite_schema_id', '')}",
        f"Suite schema path: {report.get('suite_schema_path', '')}",
        f"Suite schema sha256: {report.get('suite_schema_sha256', '')}",
        f"Task count: {report.get('task_count', 0)}",
        f"Valid: {report.get('valid', False)}",
        f"Error count: {report.get('error_count', 0)}",
        f"Warning count: {report.get('warning_count', 0)}",
        "",
        "## Errors",
        "",
    ]
    if report.get("errors"):
        lines.extend(_format_issue(issue) for issue in report["errors"])
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if report.get("warnings"):
        lines.extend(_format_issue(issue) for issue in report["warnings"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_eval_suite_validation(report: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "suite-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "suite-validation.md").write_text(eval_suite_validation_to_markdown(report), encoding="utf-8")
    return output_dir


def _validate_top_level(payload: dict[str, Any], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    if not isinstance(payload.get("tasks"), list):
        errors.append(_issue("tasks", "invalid_type", "tasks must be a list."))
        return
    if not payload["tasks"]:
        errors.append(_issue("tasks", "empty", "tasks must contain at least one eval task."))
    schema_version = payload.get("schema_version")
    if schema_version is None:
        warnings.append(_issue("schema_version", "missing", "schema_version is missing; defaulting to unversioned."))
    elif not isinstance(schema_version, str):
        errors.append(_issue("schema_version", "invalid_type", "schema_version must be a string."))
    elif schema_version not in SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS))
        errors.append(
            _issue(
                "schema_version",
                "unsupported",
                f"Unsupported schema_version: {schema_version}. Supported versions: {supported}.",
            )
        )
    suite = payload.get("suite") or payload.get("name")
    if suite is not None and not isinstance(suite, str):
        errors.append(_issue("suite", "invalid_type", "suite/name must be a string when present."))


def _load_eval_suite_payload(path: str | Path) -> dict[str, Any]:
    suite_path = Path(path)
    if suite_path.is_dir():
        suite_path = suite_path / "targeted-eval-suite.json"
    if not suite_path.exists():
        raise FileNotFoundError(f"Missing eval suite: {suite_path}")
    payload = json.loads(suite_path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return {"suite": "custom-json-list", "tasks": payload, "task_count": len(payload)}
    if not isinstance(payload, dict):
        raise TypeError("Eval suite payload must be a JSON object or list.")
    return payload


def _task_spec_payload(item: Any, index: int, errors: list[dict[str, Any]]) -> dict[str, Any] | None:
    path = f"tasks[{index}]"
    if not isinstance(item, dict):
        errors.append(_issue(path, "invalid_type", "task entry must be an object."))
        return None
    if "task_spec" in item:
        if not isinstance(item["task_spec"], dict):
            errors.append(_issue(f"{path}.task_spec", "invalid_type", "task_spec must be an object."))
            return None
        return item["task_spec"]
    return item


def _merged_tool_schemas(
    payload: dict[str, Any],
    explicit_tool_schemas: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for tool_name, schema in _suite_local_tool_schemas(payload).items():
        merged[tool_name] = schema
    if explicit_tool_schemas:
        for tool_name, schema in explicit_tool_schemas.items():
            if tool_name and isinstance(schema, dict):
                merged[str(tool_name)] = schema
    return merged


def _suite_local_tool_schemas(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    tasks = payload.get("tasks", [])
    if not isinstance(tasks, list):
        return schemas
    for item in tasks:
        if not isinstance(item, dict):
            continue
        raw_schemas = item.get("tool_schemas")
        if not isinstance(raw_schemas, dict):
            continue
        for tool_name, schema in raw_schemas.items():
            if tool_name and isinstance(schema, dict):
                schemas[str(tool_name)] = schema
    return schemas


def _validate_task_spec(
    task_spec: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    seen_ids: set[str],
    available_tools: set[str] | None = None,
    available_quality_gates: set[str] | None = None,
    tool_schemas: dict[str, dict[str, Any]] | None = None,
) -> None:
    allowed_fields = {field_info.name for field_info in fields(EvalTaskSpec)}
    unknown_fields = sorted(set(task_spec) - allowed_fields)
    for field_name in unknown_fields:
        warnings.append(_issue(f"{path}.{field_name}", "unknown_field", "Unknown EvalTaskSpec field will be ignored."))
    task_id = task_spec.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append(_issue(f"{path}.id", "missing_or_invalid", "id must be a non-empty string."))
    elif task_id in seen_ids:
        errors.append(_issue(f"{path}.id", "duplicate", f"Duplicate task id: {task_id}"))
    else:
        seen_ids.add(task_id)
    prompt = task_spec.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(_issue(f"{path}.prompt", "missing_or_invalid", "prompt must be a non-empty string."))
    for field_name in LIST_FIELDS:
        if field_name in task_spec and not isinstance(task_spec[field_name], list):
            errors.append(_issue(f"{path}.{field_name}", "invalid_type", f"{field_name} must be a list."))
        elif field_name in task_spec and field_name in STRING_LIST_FIELDS:
            _validate_string_list(task_spec[field_name], f"{path}.{field_name}", errors)
            if field_name == "expected_artifacts":
                _validate_artifact_path_list(task_spec[field_name], f"{path}.{field_name}", errors)
        elif field_name == "requirement_criteria" and field_name in task_spec:
            _validate_requirement_criteria(
                task_spec[field_name],
                f"{path}.{field_name}",
                errors,
                available_tools=available_tools,
            )
    for field_name in DICT_FIELDS:
        if field_name in task_spec and not isinstance(task_spec[field_name], dict):
            errors.append(_issue(f"{path}.{field_name}", "invalid_type", f"{field_name} must be an object."))
    for field_name in BOOL_FIELDS:
        if field_name in task_spec and not isinstance(task_spec[field_name], bool):
            errors.append(_issue(f"{path}.{field_name}", "invalid_type", f"{field_name} must be a boolean."))
    for field_name in INT_FIELDS:
        if field_name not in task_spec or task_spec[field_name] is None:
            continue
        if not isinstance(task_spec[field_name], int) or isinstance(task_spec[field_name], bool):
            errors.append(_issue(f"{path}.{field_name}", "invalid_type", f"{field_name} must be an integer or null."))
            continue
        if task_spec[field_name] < 0:
            errors.append(_issue(f"{path}.{field_name}", "invalid_value", f"{field_name} cannot be negative."))
    if isinstance(task_spec.get("max_turns"), int) and task_spec["max_turns"] < 1:
        errors.append(_issue(f"{path}.max_turns", "invalid_value", "max_turns must be at least 1."))
    _validate_required_tool_arguments(task_spec, path, errors, available_tools=available_tools, tool_schemas=tool_schemas)
    _validate_tool_references(task_spec, path, errors, available_tools)
    _validate_quality_gate_references(task_spec, path, errors, available_quality_gates)


def _validate_string_list(values: list[Any], path: str, errors: list[dict[str, Any]]) -> None:
    for index, item in enumerate(values):
        if not isinstance(item, str) or not item:
            errors.append(_issue(f"{path}[{index}]", "invalid_type", "list item must be a non-empty string."))


def _validate_requirement_criteria(
    values: list[Any],
    path: str,
    errors: list[dict[str, Any]],
    *,
    available_tools: set[str] | None = None,
) -> None:
    string_fields = {
        "id",
        "text",
        "requirement",
        "required_source_type",
        "source_type",
        "required_source_ref",
        "source_ref",
        "min_strength",
        "required_artifact_path",
        "artifact_path",
        "required_tool",
        "tool_name",
    }
    verifier_fields = {
        "text",
        "requirement",
        "required_source_type",
        "source_type",
        "required_source_ref",
        "source_ref",
        "min_strength",
        "required_artifact_path",
        "artifact_path",
        "required_tool",
        "tool_name",
    }
    for index, item in enumerate(values):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(_issue(item_path, "invalid_type", "list item must be an object."))
            continue
        for field_name in sorted(string_fields & set(item)):
            if not isinstance(item[field_name], str) or not item[field_name].strip():
                errors.append(_issue(f"{item_path}.{field_name}", "invalid_type", f"{field_name} must be a non-empty string when present."))
        if not any(isinstance(item.get(field_name), str) and item.get(field_name, "").strip() for field_name in verifier_fields):
            errors.append(
                _issue(
                    item_path,
                    "empty_requirement_criterion",
                    "requirement criterion must declare text, evidence, artifact, or tool verification.",
                )
            )
        required_tool = item.get("required_tool") or item.get("tool_name")
        if isinstance(required_tool, str) and available_tools is not None and required_tool not in available_tools:
            errors.append(_issue(f"{item_path}.required_tool", "unknown_tool", f"Unknown tool referenced: {required_tool}"))
        for field_name in ("required_artifact_path", "artifact_path"):
            if isinstance(item.get(field_name), str):
                _validate_artifact_path(item[field_name], f"{item_path}.{field_name}", errors)


def _validate_artifact_path_list(values: list[Any], path: str, errors: list[dict[str, Any]]) -> None:
    for index, item in enumerate(values):
        if isinstance(item, str):
            _validate_artifact_path(item, f"{path}[{index}]", errors)


def _validate_artifact_path(value: str, path: str, errors: list[dict[str, Any]]) -> None:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("~"):
        errors.append(_issue(path, "invalid_artifact_path", "artifact path must be a portable relative path."))
        return
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        errors.append(_issue(path, "invalid_artifact_path", "artifact path must not include a Windows drive prefix."))
        return
    if any(part == ".." for part in normalized.split("/")):
        errors.append(_issue(path, "invalid_artifact_path", "artifact path must not contain parent traversal."))


def _validate_required_tool_arguments(
    task_spec: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
    *,
    available_tools: set[str] | None = None,
    tool_schemas: dict[str, dict[str, Any]] | None = None,
) -> None:
    required_tool_arguments = task_spec.get("required_tool_arguments")
    if not isinstance(required_tool_arguments, list):
        return
    for index, item in enumerate(required_tool_arguments):
        item_path = f"{path}.required_tool_arguments[{index}]"
        if not isinstance(item, dict):
            errors.append(_issue(item_path, "invalid_type", "required tool argument entry must be an object."))
            continue
        tool_name = item.get("tool") or item.get("tool_name")
        if tool_name is not None and not isinstance(tool_name, str):
            errors.append(_issue(f"{item_path}.tool", "invalid_type", "tool/tool_name must be a string when present."))
        elif isinstance(tool_name, str) and available_tools is not None and tool_name not in available_tools:
            errors.append(_issue(f"{item_path}.tool", "unknown_tool", f"Unknown tool referenced: {tool_name}"))
        arguments = item.get("arguments") if "arguments" in item else item.get("args")
        if arguments is not None and not isinstance(arguments, dict):
            errors.append(_issue(f"{item_path}.arguments", "invalid_type", "arguments/args must be an object when present."))
            continue
        if isinstance(tool_name, str) and isinstance(arguments, dict) and tool_schemas and tool_name in tool_schemas:
            _validate_tool_argument_expectations(
                arguments,
                tool_schemas[tool_name],
                f"{item_path}.arguments",
                errors,
            )


def _validate_tool_argument_expectations(
    arguments: dict[str, Any],
    schema: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
) -> None:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    for key, expected in arguments.items():
        key_path = f"{path}.{key}"
        child_schema = properties.get(key)
        if not isinstance(child_schema, dict):
            errors.append(_issue(key_path, "unknown_tool_argument", f"Tool schema has no argument named {key!r}."))
            continue
        _validate_expected_argument_value(expected, child_schema, key_path, errors)


def _validate_expected_argument_value(
    expected: Any,
    schema: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
) -> None:
    if _is_predicate(expected):
        _validate_argument_predicate(expected, schema, path, errors)
        return
    if isinstance(expected, dict) and _schema_accepts_object(schema):
        properties = _schema_properties(schema)
        if properties:
            _validate_tool_argument_expectations(expected, {"properties": properties}, path, errors)
            return
    _validate_literal_argument_value(expected, schema, path, errors)


def _validate_argument_predicate(
    predicate: dict[str, Any],
    schema: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
) -> None:
    unknown_keys = sorted(set(predicate) - PREDICATE_KEYS)
    for key in unknown_keys:
        errors.append(_issue(f"{path}.{key}", "unknown_tool_argument_predicate", f"Unknown argument predicate: {key}"))
    if "equals" in predicate:
        _validate_literal_argument_value(predicate["equals"], schema, f"{path}.equals", errors)
    if "in" in predicate:
        values = predicate["in"]
        if not isinstance(values, list):
            errors.append(_issue(f"{path}.in", "invalid_type", "in predicate must be a list."))
        else:
            for index, value in enumerate(values):
                _validate_literal_argument_value(value, schema, f"{path}.in[{index}]", errors)
    for key in ("contains", "startswith", "endswith"):
        if key not in predicate:
            continue
        if not isinstance(predicate[key], str):
            errors.append(_issue(f"{path}.{key}", "invalid_type", f"{key} predicate value must be a string."))
            continue
        if not _schema_accepts_text_predicate(schema):
            errors.append(
                _issue(
                    f"{path}.{key}",
                    "tool_argument_predicate_type_mismatch",
                    f"{key} predicate requires a string, array, or object-compatible argument schema.",
                )
            )


def _validate_literal_argument_value(value: Any, schema: dict[str, Any], path: str, errors: list[dict[str, Any]]) -> None:
    result = ToolArgumentSchemaValidator().validate(schema, value, path="$")
    if result.passed:
        return
    errors.append(
        _issue(
            path,
            "tool_argument_schema_mismatch",
            "Expected value does not match tool argument schema: " + "; ".join(result.errors),
        )
    )


def _is_predicate(value: Any) -> bool:
    return isinstance(value, dict) and bool(set(value) & PREDICATE_KEYS)


def _schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if isinstance(properties, dict):
        return properties
    for branch in schema.get("oneOf", []):
        if isinstance(branch, dict):
            properties = branch.get("properties")
            if isinstance(properties, dict):
                return properties
    return {}


def _schema_types(schema: dict[str, Any]) -> set[str]:
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        return {schema_type}
    if isinstance(schema_type, list):
        return {item for item in schema_type if isinstance(item, str)}
    types: set[str] = set()
    for branch in schema.get("oneOf", []):
        if isinstance(branch, dict):
            types.update(_schema_types(branch))
    return types


def _schema_accepts_object(schema: dict[str, Any]) -> bool:
    types = _schema_types(schema)
    return not types or "object" in types or bool(_schema_properties(schema))


def _schema_accepts_text_predicate(schema: dict[str, Any]) -> bool:
    types = _schema_types(schema)
    return not types or bool(types & {"string", "array", "object"})


def _validate_tool_references(
    task_spec: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
    available_tools: set[str] | None,
) -> None:
    if available_tools is None:
        return
    for field_name in ("allowed_tools", "required_tools", "forbidden_tools", "required_tool_order"):
        values = task_spec.get(field_name, [])
        if not isinstance(values, list):
            continue
        for index, tool_name in enumerate(values):
            if isinstance(tool_name, str) and tool_name not in available_tools:
                errors.append(_issue(f"{path}.{field_name}[{index}]", "unknown_tool", f"Unknown tool referenced: {tool_name}"))


def _validate_quality_gate_references(
    task_spec: dict[str, Any],
    path: str,
    errors: list[dict[str, Any]],
    available_quality_gates: set[str] | None,
) -> None:
    if available_quality_gates is None:
        return
    quality_gates = task_spec.get("quality_gates", [])
    if not isinstance(quality_gates, list):
        return
    for index, gate_name in enumerate(quality_gates):
        if isinstance(gate_name, str) and gate_name not in available_quality_gates:
            errors.append(_issue(f"{path}.quality_gates[{index}]", "unknown_quality_gate", f"Unknown quality gate referenced: {gate_name}"))


def _validation_report(
    *,
    path: str | Path,
    payload: dict[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    schema_snapshot = suite_schema_snapshot_metadata()
    return {
        "path": str(path),
        "suite": payload.get("suite") or payload.get("name") or "",
        "schema_version": payload.get("schema_version", "unversioned"),
        "supported_schema_versions": sorted(SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS),
        **schema_snapshot,
        "task_count": len(payload.get("tasks", [])) if isinstance(payload.get("tasks"), list) else 0,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def suite_schema_snapshot_metadata() -> dict[str, str]:
    if not SUITE_SCHEMA_SNAPSHOT_PATH.exists():
        return {
            "suite_schema_id": "",
            "suite_schema_path": str(SUITE_SCHEMA_SNAPSHOT_PATH),
            "suite_schema_sha256": "",
        }
    raw = SUITE_SCHEMA_SNAPSHOT_PATH.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except json.JSONDecodeError:
        payload = {}
    schema_id = payload.get("$id", "") if isinstance(payload, dict) else ""
    return {
        "suite_schema_id": str(schema_id),
        "suite_schema_path": str(SUITE_SCHEMA_SNAPSHOT_PATH),
        "suite_schema_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _format_issue(issue: dict[str, Any]) -> str:
    return f"- `{issue.get('path', '')}` [{issue.get('code', '')}]: {issue.get('message', '')}"
