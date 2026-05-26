"""Tests for tool argument type coercion."""

from __future__ import annotations

import pytest

from metis.tools.coerce import coerce_arguments


class TestIntegerCoercion:
    def test_string_to_int(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        result = coerce_arguments(schema, {"n": "42"})
        assert result["n"] == 42

    def test_float_to_int(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        result = coerce_arguments(schema, {"n": 3.14})
        assert result["n"] == 3

    def test_int_unchanged(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        result = coerce_arguments(schema, {"n": 42})
        assert result["n"] == 42

    def test_invalid_string_kept(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        result = coerce_arguments(schema, {"n": "abc"})
        assert result["n"] == "abc"


class TestNumberCoercion:
    def test_string_to_float(self):
        schema = {"type": "object", "properties": {"x": {"type": "number"}}}
        result = coerce_arguments(schema, {"x": "3.14"})
        assert result["x"] == 3.14

    def test_int_to_float(self):
        schema = {"type": "object", "properties": {"x": {"type": "number"}}}
        result = coerce_arguments(schema, {"x": 5})
        assert result["x"] == 5.0


class TestBooleanCoercion:
    def test_string_true(self):
        schema = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
        for val in ("true", "True", "TRUE", "yes", "1", "on"):
            result = coerce_arguments(schema, {"flag": val})
            assert result["flag"] is True, f"failed for {val}"

    def test_string_false(self):
        schema = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
        for val in ("false", "False", "FALSE", "no", "0", "off"):
            result = coerce_arguments(schema, {"flag": val})
            assert result["flag"] is False, f"failed for {val}"

    def test_int_to_bool(self):
        schema = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
        assert coerce_arguments(schema, {"flag": 1})["flag"] is True
        assert coerce_arguments(schema, {"flag": 0})["flag"] is False


class TestStringCoercion:
    def test_int_to_string(self):
        schema = {"type": "object", "properties": {"s": {"type": "string"}}}
        result = coerce_arguments(schema, {"s": 42})
        assert result["s"] == "42"

    def test_none_to_string(self):
        schema = {"type": "object", "properties": {"s": {"type": "string"}}}
        result = coerce_arguments(schema, {"s": None})
        assert result["s"] == ""


class TestNestedCoercion:
    def test_nested_object(self):
        schema = {
            "type": "object",
            "properties": {
                "inner": {
                    "type": "object",
                    "properties": {"n": {"type": "integer"}},
                }
            },
        }
        result = coerce_arguments(schema, {"inner": {"n": "5"}})
        assert result["inner"]["n"] == 5

    def test_array_items(self):
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "integer"},
                }
            },
        }
        result = coerce_arguments(schema, {"items": ["1", "2", "3"]})
        assert result["items"] == [1, 2, 3]


class TestNoSchemaProperties:
    def test_no_properties_unchanged(self):
        schema = {"type": "object"}
        result = coerce_arguments(schema, {"n": "42"})
        assert result["n"] == "42"

    def test_extra_keys_unchanged(self):
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        result = coerce_arguments(schema, {"a": "1", "b": "2"})
        assert result["a"] == 1
        assert result["b"] == "2"
