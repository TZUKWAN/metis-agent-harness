"""Tests for metis/runtime/errors.py and metis/runtime/response.py."""

import pytest

from metis.runtime.errors import MetisError, ProviderError, ToolDispatchError, ParserError, QualityGateError
from metis.runtime.response import ToolCall, ToolResult, NormalizedResponse, AgentRunRequest, AgentRunResult


class TestErrors:
    def test_metis_error_is_exception(self):
        assert issubclass(MetisError, Exception)

    def test_provider_error_is_metis_error(self):
        assert issubclass(ProviderError, MetisError)
        e = ProviderError("api timeout")
        assert str(e) == "api timeout"

    def test_tool_dispatch_error_is_metis_error(self):
        assert issubclass(ToolDispatchError, MetisError)

    def test_parser_error_is_metis_error(self):
        assert issubclass(ParserError, MetisError)

    def test_quality_gate_error_is_metis_error(self):
        assert issubclass(QualityGateError, MetisError)

    def test_errors_can_be_caught_as_base(self):
        with pytest.raises(MetisError):
            raise ProviderError("fail")


class TestToolCall:
    def test_basic_creation(self):
        tc = ToolCall(name="read_file", arguments={"path": "a.txt"})
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "a.txt"}
        assert tc.id == ""
        assert tc.raw is None

    def test_with_id(self):
        tc = ToolCall(name="x", arguments={}, id="call_123", raw={"original": True})
        assert tc.id == "call_123"
        assert tc.raw == {"original": True}


class TestToolResult:
    def test_success_result(self):
        tr = ToolResult(tool_name="read_file", content="hello")
        assert not tr.failed
        assert tr.status == "ok"
        assert tr.error is None

    def test_failed_result_by_status(self):
        tr = ToolResult(tool_name="read_file", content="", status="error")
        assert tr.failed

    def test_failed_result_by_error(self):
        tr = ToolResult(tool_name="read_file", content="", error="file not found")
        assert tr.failed

    def test_metadata_default(self):
        tr = ToolResult(tool_name="x", content="")
        assert tr.metadata == {}


class TestNormalizedResponse:
    def test_defaults(self):
        r = NormalizedResponse()
        assert r.content == ""
        assert r.reasoning is None
        assert r.tool_calls == []
        assert r.finish_reason == ""
        assert r.usage == {}

    def test_with_tool_calls(self):
        r = NormalizedResponse(
            content="done",
            tool_calls=[ToolCall(name="read_file", arguments={"path": "a"})],
            finish_reason="stop",
        )
        assert len(r.tool_calls) == 1


class TestAgentRunRequest:
    def test_defaults(self):
        req = AgentRunRequest(messages=[{"role": "user", "content": "hi"}])
        assert req.max_turns == 12
        assert req.session_id == "default"
        assert req.allowed_tools is None

    def test_custom_values(self):
        req = AgentRunRequest(
            messages=[],
            max_turns=5,
            session_id="abc",
            allowed_tools=["read_file"],
        )
        assert req.max_turns == 5
        assert req.session_id == "abc"


class TestAgentRunResult:
    def test_defaults(self):
        result = AgentRunResult(status="done")
        assert result.final_text == ""
        assert result.turns_used == 0
        assert result.tool_results == []
        assert result.errors == []

    def test_with_results(self):
        result = AgentRunResult(
            status="done",
            final_text="task completed",
            turns_used=3,
            tool_results=[ToolResult(tool_name="x", content="ok")],
        )
        assert result.turns_used == 3
        assert len(result.tool_results) == 1
