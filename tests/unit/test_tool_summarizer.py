"""Tests for tool result summarizer."""

from __future__ import annotations

import json

import pytest

from metis.tools.summarizer import summarize_tool_result


class TestSummarizeDict:
    def test_short_dict_unchanged(self):
        data = json.dumps({"path": "/tmp", "exists": True})
        result = summarize_tool_result(data, "path_exists")
        assert result == data

    def test_large_dict_summarized(self):
        data = json.dumps({"path": "/tmp", "content": "x" * 5000})
        result = summarize_tool_result(data, "read_file")
        assert len(result) < len(data)
        assert "content:" in result

    def test_dict_with_list_field(self):
        data = json.dumps({"files": [{"name": f"f{i}"} for i in range(100)]})
        result = summarize_tool_result(data, "list_directory")
        assert "files: [100 items]" in result


class TestSummarizeList:
    def test_short_list_unchanged(self):
        data = json.dumps([1, 2, 3])
        result = summarize_tool_result(data, "test")
        assert result == data

    def test_large_list_summarized(self):
        data = json.dumps(list(range(200)))
        result = summarize_tool_result(data, "test")
        assert "[200 items]" in result


class TestSummarizeText:
    def test_short_text_unchanged(self):
        text = "hello world"
        result = summarize_tool_result(text, "echo")
        assert result == text

    def test_long_text_summarized(self):
        text = "\n".join(f"line {i}" for i in range(500))
        result = summarize_tool_result(text, "cat")
        assert "[cat] Summary" in result
        assert "500 lines" in result

    def test_max_chars_boundary(self):
        text = "a" * 700
        result = summarize_tool_result(text, "test")
        assert result == text
        text = "a" * 900
        result = summarize_tool_result(text, "test")
        assert result != text


class TestEdgeCases:
    def test_empty_string(self):
        assert summarize_tool_result("", "test") == ""

    def test_json_with_nested_dict(self):
        data = json.dumps({"outer": {"inner": "x" * 3000}})
        result = summarize_tool_result(data, "test")
        assert len(result) < len(data)
