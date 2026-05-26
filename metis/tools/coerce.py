"""Automatic type coercion for tool arguments before schema validation."""

from __future__ import annotations

from typing import Any


def coerce_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    """Coerce argument values to match expected schema types."""
    if not isinstance(arguments, dict):
        return arguments
    coerced = dict(arguments)
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return coerced
    for key, prop_schema in properties.items():
        if key not in coerced:
            continue
        coerced[key] = _coerce_value(prop_schema, coerced[key])
    return coerced


def _coerce_value(schema: dict[str, Any], value: Any) -> Any:
    expected_type = schema.get("type")
    if expected_type == "integer":
        return _to_int(value)
    if expected_type == "number":
        return _to_float(value)
    if expected_type == "boolean":
        return _to_bool(value)
    if expected_type == "string":
        return _to_str(value)
    if expected_type == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            return [_coerce_value(item_schema, item) for item in value]
        return value
    if expected_type == "object" and isinstance(value, dict):
        return coerce_arguments(schema, value)
    return value


def _to_int(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    if isinstance(value, float):
        return int(value)
    return value


def _to_float(value: Any) -> Any:
    if isinstance(value, float):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def _to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "1", "on"):
            return True
        if lowered in ("false", "no", "0", "off"):
            return False
    if isinstance(value, int) and not isinstance(value, bool):
        return value != 0
    return value


def _to_str(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)
