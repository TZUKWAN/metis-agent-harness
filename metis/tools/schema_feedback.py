"""Schema validation feedback helpers for tool repair loops."""

from __future__ import annotations

from typing import Any


def schema_repair_feedback(schema_errors: Any) -> dict[str, list[str]]:
    typed_hints = schema_repair_hint_details(schema_errors)
    return {
        "hints": [item["hint_text"] for item in typed_hints],
        "hint_types": [item["hint_type"] for item in typed_hints],
        "details": typed_hints,
    }


def schema_repair_hints(schema_errors: Any) -> list[str]:
    return schema_repair_feedback(schema_errors)["hints"]


def schema_repair_hint_types(schema_errors: Any) -> list[str]:
    return schema_repair_feedback(schema_errors)["hint_types"]


def schema_repair_hint_details(schema_errors: Any) -> list[dict[str, Any]]:
    if not isinstance(schema_errors, list):
        return []
    hints: list[dict[str, Any]] = []
    for raw_error in schema_errors:
        error = str(raw_error)
        lowered = error.lower()
        path = error.split(":", 1)[0]
        if "additional property not allowed" in lowered:
            hints.append(_hint("remove_additional_property", path, "additionalProperties", error, f"Remove the unsupported argument at {path}."))
        elif "missing required property" in lowered:
            hints.append(_hint("add_required_property", path, "required", error, f"Add the required argument {path}."))
        elif "less than minitems" in lowered:
            hints.append(_hint("increase_array_items", path, "minItems", error, f"Provide enough array items for {path}; do not pass an empty array."))
        elif "exceeds maxitems" in lowered:
            hints.append(_hint("reduce_array_items", path, "maxItems", error, f"Reduce the number of array items for {path}."))
        elif "expected " in lowered and " got " in lowered:
            detail = error.split(":", 1)[1].strip() if ":" in error else error
            hints.append(_hint("fix_type", path, "type", error, f"Change {path} so it matches the schema type: {detail}."))
        elif "less than minimum" in lowered or "greater than exclusiveminimum" in lowered:
            keyword = "exclusiveMinimum" if "exclusiveminimum" in lowered else "minimum"
            hints.append(_hint("increase_numeric_value", path, keyword, error, f"Increase the numeric value for {path} to satisfy the schema bound."))
        elif "exceeds maximum" in lowered or "less than exclusivemaximum" in lowered:
            keyword = "exclusiveMaximum" if "exclusivemaximum" in lowered else "maximum"
            hints.append(_hint("reduce_numeric_value", path, keyword, error, f"Reduce the numeric value for {path} to satisfy the schema bound."))
        elif "does not match pattern" in lowered:
            hints.append(_hint("fix_string_pattern", path, "pattern", error, f"Rewrite {path} so it matches the required string pattern."))
        elif "not in enum" in lowered:
            hints.append(_hint("use_enum_value", path, "enum", error, f"Use one of the allowed enum values for {path}."))
        elif "oneof schema" in lowered:
            hints.append(_hint("fix_one_of_branch", path, "oneOf", error, f"Rewrite {path} so exactly one allowed schema branch matches."))
    return hints


def _hint(hint_type: str, path: str, keyword: str, error: str, hint: str) -> dict[str, Any]:
    return {
        "hint_type": hint_type,
        "schema_path": path,
        "schema_keyword": keyword,
        "schema_error": error,
        "hint_text": hint,
    }
