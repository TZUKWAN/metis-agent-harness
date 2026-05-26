"""Tests for metis/tools/failures.py."""

from metis.tools.failures import ToolFailureType, tool_failure_metadata


class TestToolFailureType:
    def test_all_types_have_values(self):
        assert ToolFailureType.UNKNOWN_TOOL == "unknown_tool"
        assert ToolFailureType.SCHEMA_VALIDATION_FAILED == "schema_validation_failed"
        assert ToolFailureType.COMMAND_FAILED == "command_failed"
        assert ToolFailureType.RUNTIME_ERROR == "runtime_error"

    def test_is_str_enum(self):
        assert isinstance(ToolFailureType.UNKNOWN_TOOL, str)


class TestToolFailureMetadata:
    def test_basic_metadata(self):
        meta = tool_failure_metadata(ToolFailureType.UNKNOWN_TOOL)
        assert meta["failure_type"] == "unknown_tool"
        assert "repair_instruction" in meta
        assert meta["recoverable"] is True
        assert meta["retry_allowed"] is True

    def test_non_recoverable_failure(self):
        meta = tool_failure_metadata(ToolFailureType.POLICY_DENIED)
        assert meta["recoverable"] is False
        assert meta["retry_allowed"] is False

    def test_override_retry_allowed(self):
        meta = tool_failure_metadata(ToolFailureType.POLICY_DENIED, retry_allowed=True)
        assert meta["retry_allowed"] is True

    def test_extra_fields(self):
        meta = tool_failure_metadata(ToolFailureType.COMMAND_FAILED, extra={"exit_code": 1})
        assert meta["exit_code"] == 1

    def test_all_types_have_instructions(self):
        for ft in ToolFailureType:
            meta = tool_failure_metadata(ft)
            assert meta["repair_instruction"]
            assert isinstance(meta["recoverable"], bool)

    def test_all_types_have_recoverable(self):
        for ft in ToolFailureType:
            meta = tool_failure_metadata(ft)
            assert "recoverable" in meta
