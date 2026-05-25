"""Small JSON-schema subset validator for tool arguments."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SchemaValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


class ToolArgumentSchemaValidator:
    """Validate tool arguments against the JSON-schema subset used by ToolSpec."""

    def validate(self, schema: dict[str, Any], value: Any, *, path: str = "$") -> SchemaValidationResult:
        errors = self._validate(schema, value, path)
        return SchemaValidationResult(not errors, errors)

    def _validate(self, schema: dict[str, Any], value: Any, path: str) -> list[str]:
        if "oneOf" in schema:
            branch_errors = [self._validate(branch, value, path) for branch in schema["oneOf"]]
            matching_branches = [index for index, errors in enumerate(branch_errors) if not errors]
            if len(matching_branches) == 1:
                return []
            if len(matching_branches) > 1:
                return [f"{path}: value matched multiple oneOf schemas: {matching_branches}"]
            details = "; ".join(f"branch {index}: {', '.join(errors)}" for index, errors in enumerate(branch_errors))
            return [f"{path}: value did not match exactly one oneOf schema ({details})"]

        errors: list[str] = []
        expected_type = schema.get("type")
        if expected_type is not None and not self._matches_type(expected_type, value):
            return [f"{path}: expected {expected_type}, got {type(value).__name__}"]

        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{path}: value {value!r} not in enum {schema['enum']!r}")

        if isinstance(value, str):
            errors.extend(self._validate_string_constraints(schema, value, path))

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            errors.extend(self._validate_number_constraints(schema, value, path))

        if expected_type == "object" or (expected_type is None and isinstance(value, dict)):
            if not isinstance(value, dict):
                return errors
            required = schema.get("required", [])
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key}: missing required property")
            properties = schema.get("properties", {})
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(self._validate(child_schema, value[key], f"{path}.{key}"))
            errors.extend(self._validate_additional_properties(schema, value, path))

        if expected_type == "array" and isinstance(value, list):
            errors.extend(self._validate_array_constraints(schema, value, path))
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    errors.extend(self._validate(item_schema, item, f"{path}[{index}]"))

        return errors

    def _validate_string_constraints(self, schema: dict[str, Any], value: str, path: str) -> list[str]:
        errors: list[str] = []
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path}: length {len(value)} is less than minLength {min_length}")
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(f"{path}: length {len(value)} exceeds maxLength {max_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if re.search(pattern, value) is None:
                    errors.append(f"{path}: value {value!r} does not match pattern {pattern!r}")
            except re.error as exc:
                errors.append(f"{path}: invalid schema pattern {pattern!r}: {exc}")
        return errors

    def _validate_number_constraints(self, schema: dict[str, Any], value: int | float, path: str) -> list[str]:
        errors: list[str] = []
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool) and value < minimum:
            errors.append(f"{path}: value {value!r} is less than minimum {minimum!r}")
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and not isinstance(maximum, bool) and value > maximum:
            errors.append(f"{path}: value {value!r} exceeds maximum {maximum!r}")
        exclusive_minimum = schema.get("exclusiveMinimum")
        if isinstance(exclusive_minimum, (int, float)) and not isinstance(exclusive_minimum, bool) and value <= exclusive_minimum:
            errors.append(f"{path}: value {value!r} must be greater than exclusiveMinimum {exclusive_minimum!r}")
        exclusive_maximum = schema.get("exclusiveMaximum")
        if isinstance(exclusive_maximum, (int, float)) and not isinstance(exclusive_maximum, bool) and value >= exclusive_maximum:
            errors.append(f"{path}: value {value!r} must be less than exclusiveMaximum {exclusive_maximum!r}")
        return errors

    def _validate_array_constraints(self, schema: dict[str, Any], value: list[Any], path: str) -> list[str]:
        errors: list[str] = []
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: item count {len(value)} is less than minItems {min_items}")
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path}: item count {len(value)} exceeds maxItems {max_items}")
        return errors

    def _validate_additional_properties(self, schema: dict[str, Any], value: dict[str, Any], path: str) -> list[str]:
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
        pattern_properties = schema.get("patternProperties", {})
        if not isinstance(pattern_properties, dict):
            pattern_properties = {}
        additional = schema.get("additionalProperties", True)
        errors: list[str] = []
        for key, item in value.items():
            if key in properties:
                continue
            matched_schema = self._matching_pattern_schema(pattern_properties, key, f"{path}.{key}", errors)
            if matched_schema is not None:
                errors.extend(self._validate(matched_schema, item, f"{path}.{key}"))
                continue
            if additional is False:
                errors.append(f"{path}.{key}: additional property not allowed")
            elif isinstance(additional, dict):
                errors.extend(self._validate(additional, item, f"{path}.{key}"))
        return errors

    @staticmethod
    def _matching_pattern_schema(
        pattern_properties: dict[str, Any],
        key: str,
        path: str,
        errors: list[str],
    ) -> dict[str, Any] | None:
        for pattern, child_schema in pattern_properties.items():
            if not isinstance(pattern, str) or not isinstance(child_schema, dict):
                continue
            try:
                if re.search(pattern, key):
                    return child_schema
            except re.error as exc:
                errors.append(f"{path}: invalid schema patternProperty {pattern!r}: {exc}")
        return None

    @staticmethod
    def _matches_type(expected_type: str | list[str], value: Any) -> bool:
        if isinstance(expected_type, list):
            return any(ToolArgumentSchemaValidator._matches_type(item, value) for item in expected_type)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "null":
            return value is None
        return True
