"""Tests for tool input sanitizer."""

from __future__ import annotations

import pytest

from metis.tools.sanitizer import ToolInputSanitizer


@pytest.fixture
def sanitizer():
    return ToolInputSanitizer()


class TestStringSanitization:
    def test_null_bytes_stripped(self, sanitizer):
        result = sanitizer.sanitize({"path": "file\x00.txt"})
        assert result["path"] == "file.txt"

    def test_control_chars_stripped(self, sanitizer):
        result = sanitizer.sanitize({"content": "hello\x01\x02\x03world"})
        assert result["content"] == "helloworld"

    def test_newlines_preserved(self, sanitizer):
        result = sanitizer.sanitize({"content": "line1\nline2\r\nline3"})
        assert result["content"] == "line1\nline2\r\nline3"

    def test_tab_preserved(self, sanitizer):
        result = sanitizer.sanitize({"content": "col1\tcol2"})
        assert result["content"] == "col1\tcol2"

    def test_long_string_truncated(self, sanitizer):
        long_str = "a" * 200_000
        result = sanitizer.sanitize({"content": long_str})
        assert len(result["content"]) < 200_000
        assert result["content"].endswith("... [truncated by sanitizer]")

    def test_normal_string_unchanged(self, sanitizer):
        result = sanitizer.sanitize({"path": "/home/user/file.txt"})
        assert result["path"] == "/home/user/file.txt"

    def test_unicode_preserved(self, sanitizer):
        result = sanitizer.sanitize({"content": "Hello World"})
        assert result["content"] == "Hello World"

    def test_empty_string_unchanged(self, sanitizer):
        result = sanitizer.sanitize({"value": ""})
        assert result["value"] == ""


class TestNestedSanitization:
    def test_nested_dict(self, sanitizer):
        result = sanitizer.sanitize({"outer": {"inner": "file\x00.txt"}})
        assert result["outer"]["inner"] == "file.txt"

    def test_list_values(self, sanitizer):
        result = sanitizer.sanitize({"paths": ["a\x00b", "c\x01d"]})
        assert result["paths"] == ["ab", "cd"]

    def test_mixed_types(self, sanitizer):
        result = sanitizer.sanitize({
            "path": "file\x00.txt",
            "count": 42,
            "enabled": True,
            "items": [1, "x\x00y", None],
        })
        assert result["path"] == "file.txt"
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["items"] == [1, "xy", None]

    def test_deeply_nested(self, sanitizer):
        result = sanitizer.sanitize({"a": {"b": {"c": "deep\x00value"}}})
        assert result["a"]["b"]["c"] == "deepvalue"


class TestEdgeCases:
    def test_empty_dict(self, sanitizer):
        result = sanitizer.sanitize({})
        assert result == {}

    def test_none_values_preserved(self, sanitizer):
        result = sanitizer.sanitize({"key": None})
        assert result["key"] is None

    def test_integer_values_preserved(self, sanitizer):
        result = sanitizer.sanitize({"timeout": 30})
        assert result["timeout"] == 30

    def test_float_values_preserved(self, sanitizer):
        result = sanitizer.sanitize({"ratio": 3.14})
        assert result["ratio"] == 3.14

    def test_boolean_values_preserved(self, sanitizer):
        result = sanitizer.sanitize({"flag": True, "other": False})
        assert result["flag"] is True
        assert result["other"] is False

    def test_original_not_mutated(self, sanitizer):
        original = {"path": "file\x00.txt"}
        result = sanitizer.sanitize(original)
        assert original["path"] == "file\x00.txt"
        assert result["path"] == "file.txt"
