"""Unit tests for all provider parsers."""

import re

import pytest

from metis.providers.parsers.base import ToolCallParser
from metis.providers.parsers.hermes_xml import HermesXMLParser, TOOL_CALL_RE
from metis.providers.parsers.openai_native import OpenAINativeParser
from metis.providers.parsers.json_block import JsonBlockParser, _try_repair_json
from metis.runtime.errors import ParserError


def _hermes_wrap(json_str: str) -> str:
    """Wrap JSON in the hermes delimiters extracted from the regex pattern."""
    raw_pat = TOOL_CALL_RE.pattern
    # pattern: <prefix>\s*(\{.*?\})\s*<suffix>
    parts = raw_pat.split(r"\s*(\{.*?\})\s*")
    prefix = parts[0].replace("\\", "")
    suffix = parts[-1].replace("\\", "")
    return f"{prefix}{json_str}{suffix}"


class TestHermesXMLParser:
    def setup_method(self):
        self.parser = HermesXMLParser()

    def test_single_tool_call(self):
        text = "text " + _hermes_wrap('{"name": "read_file", "arguments": {"path": "a.txt"}}') + " rest"
        calls = self.parser.parse(text)
        assert len(calls) == 1
        assert calls[0].name == "read_file"
        assert calls[0].arguments == {"path": "a.txt"}

    def test_multiple_tool_calls(self):
        text = (
            _hermes_wrap('{"name": "read_file", "arguments": {"path": "a"}}')
            + _hermes_wrap('{"name": "write_file", "arguments": {"path": "b"}}')
        )
        calls = self.parser.parse(text)
        assert len(calls) == 2

    def test_no_tool_calls(self):
        calls = self.parser.parse("just plain text")
        assert calls == []

    def test_tool_alias(self):
        text = _hermes_wrap('{"tool": "read_file", "args": {"path": "x"}}')
        calls = self.parser.parse(text)
        assert len(calls) == 1
        assert calls[0].name == "read_file"

    def test_missing_name_raises(self):
        text = _hermes_wrap('{"arguments": {"path": "x"}}')
        with pytest.raises(ParserError):
            self.parser.parse(text)


class TestOpenAINativeParser:
    def setup_method(self):
        self.parser = OpenAINativeParser()

    def test_empty_input(self):
        assert self.parser.parse([]) == []
        assert self.parser.parse(None) == []

    def test_single_call(self):
        raw = [
            {
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "a.txt"}',
                },
            }
        ]
        calls = self.parser.parse(raw)
        assert len(calls) == 1
        assert calls[0].name == "read_file"
        assert calls[0].arguments == {"path": "a.txt"}
        assert calls[0].id == "call_123"

    def test_multiple_calls(self):
        raw = [
            {"id": "1", "function": {"name": "a", "arguments": "{}"}},
            {"id": "2", "function": {"name": "b", "arguments": "{}"}},
        ]
        calls = self.parser.parse(raw)
        assert len(calls) == 2

    def test_dict_arguments(self):
        raw = [{"id": "1", "function": {"name": "x", "arguments": {"key": "val"}}}]
        calls = self.parser.parse(raw)
        assert calls[0].arguments == {"key": "val"}

    def test_null_arguments(self):
        raw = [{"id": "1", "function": {"name": "x", "arguments": None}}]
        calls = self.parser.parse(raw)
        assert calls[0].arguments == {}


class TestJsonBlockParser:
    def setup_method(self):
        self.parser = JsonBlockParser()

    def test_fenced_json_block(self):
        text = '```json\n{"name": "read_file", "arguments": {"path": "a"}}\n```'
        calls = self.parser.parse(text)
        assert len(calls) == 1
        assert calls[0].name == "read_file"

    def test_unfenced_json_object(self):
        text = '{"name": "write_file", "arguments": {"path": "b", "content": "hi"}}'
        calls = self.parser.parse(text)
        assert len(calls) == 1

    def test_no_json(self):
        calls = self.parser.parse("just plain text no json here")
        assert calls == []

    def test_trailing_comma_repair(self):
        text = '{"name": "x", "arguments": {"a": 1,}}'
        calls = self.parser.parse(text)
        assert len(calls) == 1
        assert calls[0].arguments == {"a": 1}

    def test_tool_alias(self):
        text = '{"tool": "x", "args": {"a": 1}}'
        calls = self.parser.parse(text)
        assert len(calls) == 1
        assert calls[0].name == "x"


class TestTryRepairJson:
    def test_trailing_comma_object(self):
        result = _try_repair_json('{"a": 1,}')
        assert result == {"a": 1}

    def test_trailing_comma_array(self):
        result = _try_repair_json('{"a": [1, 2,]}')
        assert result == {"a": [1, 2]}

    def test_control_chars(self):
        result = _try_repair_json('{"a": "hello\x00world"}')
        assert result == {"a": "hello world"}

    def test_invalid_returns_none(self):
        assert _try_repair_json("not json at all") is None

    def test_strip_to_braces(self):
        result = _try_repair_json('prefix {"a": 1} suffix')
        assert result == {"a": 1}


class TestToolCallParserABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ToolCallParser()
