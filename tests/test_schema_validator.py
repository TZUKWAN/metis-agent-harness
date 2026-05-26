"""Tests for metis/tools/schema_validator.py edge cases."""

from metis.tools.schema_validator import ToolArgumentSchemaValidator


def test_null_type():
    v = ToolArgumentSchemaValidator()
    result = v.validate({"type": "null"}, None)
    assert result.passed


def test_null_type_rejects_non_null():
    v = ToolArgumentSchemaValidator()
    result = v.validate({"type": "null"}, "not null")
    assert not result.passed


def test_nested_object():
    v = ToolArgumentSchemaValidator()
    schema = {
        "type": "object",
        "properties": {
            "config": {
                "type": "object",
                "properties": {"debug": {"type": "boolean"}},
            }
        },
    }
    result = v.validate(schema, {"config": {"debug": True}})
    assert result.passed


def test_nested_object_invalid_type():
    v = ToolArgumentSchemaValidator()
    schema = {
        "type": "object",
        "properties": {
            "config": {
                "type": "object",
                "properties": {"debug": {"type": "boolean"}},
            }
        },
    }
    result = v.validate(schema, {"config": {"debug": "yes"}})
    assert not result.passed


def test_array_of_objects():
    v = ToolArgumentSchemaValidator()
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    }
    result = v.validate(schema, [{"name": "a"}, {"name": "b"}])
    assert result.passed


def test_array_missing_required():
    v = ToolArgumentSchemaValidator()
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    }
    result = v.validate(schema, [{"name": "a"}, {}])
    assert not result.passed


def test_additional_properties_false():
    v = ToolArgumentSchemaValidator()
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "additionalProperties": False,
    }
    result = v.validate(schema, {"a": "x", "extra": "y"})
    assert not result.passed


def test_enum_validation():
    v = ToolArgumentSchemaValidator()
    result = v.validate({"type": "string", "enum": ["a", "b", "c"]}, "d")
    assert not result.passed


def test_oneOf():
    v = ToolArgumentSchemaValidator()
    schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
    assert v.validate(schema, "hello").passed
    assert v.validate(schema, 42).passed
    assert not v.validate(schema, []).passed
