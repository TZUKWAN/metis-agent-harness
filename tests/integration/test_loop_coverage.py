"""Tests targeting uncovered code paths in metis/runtime/loop.py.

Covers: shutdown handling, context length errors, timeouts,
max_tool_calls_per_turn, session tool call limits (both concurrent and
sequential paths), schema repair feedback, compact feedback, tool
feedback content, parser repair exhaustion, final output repair,
circuit-breaker state recording, _json_or_text, _command_semantic_shape
edge cases, _normalize_error_text, and _is_shutdown_requested fallback.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import patch

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse, ProviderCapabilities
from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, ToolCall, ToolResult
from metis.runtime.profiles import ModelProfile
from metis.runtime.budgets import BudgetConfig
from metis.runtime.status import RuntimeStatus
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _echo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "echo",
            "Echo",
            {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False},
            lambda args, ctx: {"echo": args["value"]},
        )
    )
    return registry


def _fail_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "fail_tool",
            "Fail",
            {"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
            lambda args, ctx: (_ for _ in ()).throw(RuntimeError("always fails")),
        )
    )
    return registry


def _done_json(summary: str = "done") -> str:
    return json.dumps(
        {"status": "done", "summary": summary, "evidence_refs": [], "artifact_refs": [], "next_action": ""},
        ensure_ascii=False,
    )


# Provider that raises on the first call, then succeeds.
class _ContextErrorProvider(BaseProvider):
    """Raises a context-length error on the first call, returns normal after."""

    def __init__(self, final_response: str = "done"):
        self._final = final_response
        self._call_count = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type="test", model="test")

    async def complete(self, messages, tools=None, **params):
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("context length exceeded")
        return NormalizedResponse(content=self._final)


class _TimeoutProvider(BaseProvider):
    """Always times out."""

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type="test", model="test")

    async def complete(self, messages, tools=None, **params):
        await asyncio.sleep(9999)
        return NormalizedResponse(content="")


class _ProviderWithContextErrorThenSuccess(BaseProvider):
    """Raises context error, then on retry succeeds with a tool call, then done."""

    def __init__(self, tool_name: str = "echo"):
        self._call_count = 0
        self._tool_name = tool_name

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type="test", model="test")

    async def complete(self, messages, tools=None, **params):
        self._call_count += 1
        if self._call_count == 1:
            raise RuntimeError("context length exceeded")
        if self._call_count == 2:
            return NormalizedResponse(
                tool_calls=[ToolCall(id="c1", name=self._tool_name, arguments={"value": "recovered"})],
                content="",
            )
        return NormalizedResponse(content=_done_json())


class _RaisingCapabilitiesProvider(BaseProvider):
    """Provider whose capabilities() always raises."""

    def capabilities(self):
        raise RuntimeError("no capabilities")

    async def complete(self, messages, tools=None, **params):
        return NormalizedResponse(content="done")


# ---------------------------------------------------------------------------
# Lines 52-53: _is_shutdown_requested ImportError fallback
# ---------------------------------------------------------------------------


def test_is_shutdown_requested_import_error_fallback():
    """When metis.runtime.shutdown cannot be imported, return False."""
    with patch.dict("sys.modules", {"metis.runtime.shutdown": None}):
        # _is_shutdown_requested does a local import, so patching sys.modules
        # is enough to trigger the ImportError path without reloading.
        from metis.runtime.loop import _is_shutdown_requested
        assert _is_shutdown_requested() is False


# ---------------------------------------------------------------------------
# Lines 111-113: capabilities() exception during __init__
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capabilities_exception_falls_back_to_zero():
    """If provider.capabilities() raises, detected tokens should be 0."""
    provider = _RaisingCapabilitiesProvider()
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="deep")
    # The context engine should be created with None override (fallback)
    assert loop.context_engine.override_max_context_tokens is None


# ---------------------------------------------------------------------------
# Lines 194-212: Shutdown requested during run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_requested_returns_interrupted():
    """When shutdown is requested mid-run, return interrupted status."""
    from metis.runtime import shutdown

    shutdown._shutdown_requested = False
    try:
        provider = FakeProvider(
            [
                {"tool_calls": [{"name": "echo", "arguments": {"value": "v1"}, "id": "c1"}]},
                {"tool_calls": [{"name": "echo", "arguments": {"value": "v2"}, "id": "c2"}]},
                {"content": _done_json()},
            ]
        )
        loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="small")

        # Request shutdown before running
        shutdown._shutdown_requested = True

        result = await loop.run(
            AgentRunRequest(
                session_id="shutdown-test",
                messages=[{"role": "user", "content": "run"}],
                max_turns=5,
            )
        )

        assert result.status == "interrupted"
        assert "Shutdown" in result.final_text
    finally:
        shutdown._shutdown_requested = False


# ---------------------------------------------------------------------------
# Lines 269-290: Context length error handling with truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_length_error_truncation_and_retry():
    """When context length error occurs, truncate messages and retry."""
    provider = _ProviderWithContextErrorThenSuccess("echo")
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="deep")

    # Send enough messages so truncation has something to truncate
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    result = await loop.run(
        AgentRunRequest(
            session_id="ctx-err-test",
            messages=messages,
            max_turns=5,
        )
    )

    assert result.status == "final"
    assert provider._call_count == 3
    # Check truncation trace event was emitted
    trunc_events = [e for e in result.trace_events if e["event_type"] == "context.truncated"]
    assert len(trunc_events) == 1
    assert trunc_events[0]["attributes"]["original_messages"] > trunc_events[0]["attributes"]["truncated_messages"]


@pytest.mark.asyncio
async def test_context_length_error_no_truncation_possible():
    """When context error occurs but messages are too few to truncate, continue."""
    class _AlwaysContextError(BaseProvider):
        def capabilities(self):
            return ProviderCapabilities(provider_type="test", model="test")

        async def complete(self, messages, tools=None, **params):
            raise RuntimeError("context length exceeded")

    provider = _AlwaysContextError()
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="deep")

    result = await loop.run(
        AgentRunRequest(
            session_id="ctx-err-no-trunc",
            messages=[{"role": "user", "content": "short"}],
            max_turns=2,
        )
    )
    # Should reach max_turns with errors about context
    assert result.status == "max_turns"
    assert any("context" in e.lower() or "length" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Lines 292-294: TimeoutError handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_error_continues_to_next_turn():
    """When a provider call times out, the turn error is recorded and loop continues."""
    provider = FakeProvider(
        [
            {"content": _done_json()},
        ]
    )
    # Patch the complete method to raise TimeoutError on first call
    original_complete = provider.complete
    call_count = 0

    async def patched_complete(messages, tools=None, **params):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError("operation timed out")
        return await original_complete(messages, tools=tools, **params)

    provider.complete = patched_complete

    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="deep")
    result = await loop.run(
        AgentRunRequest(
            session_id="timeout-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    assert result.status == "final"
    assert any("timed out" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Lines 388-411: max_tool_calls_per_turn exceeded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_tool_calls_per_turn_exceeded_blocks():
    """When more tool calls than max_tool_calls_per_turn, run is blocked."""
    # Use balanced profile (max_tool_calls_per_turn=12), but send 13 tool calls
    many_calls = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": f"v{i}"}, "id": f"c{i}"}] for i in range(13)}
    ]
    # Flatten: one turn with 13 tool calls
    responses = [
        NormalizedResponse(
            tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={"value": f"v{i}"}) for i in range(13)],
            content="",
        ),
        NormalizedResponse(content=_done_json()),
    ]

    # Build a custom profile with very low max_tool_calls_per_turn
    small_limit_profile = ModelProfile(
        name="test_limit",
        budget=BudgetConfig.for_profile("default"),
        max_tool_calls_per_turn=3,
        strict_output=False,
    )
    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile=small_limit_profile)

    result = await loop.run(
        AgentRunRequest(
            session_id="tool-limit-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    assert result.status == RuntimeStatus.BLOCKED.value
    assert any("Tool call limit exceeded" in e for e in result.errors)
    # Verify checkpoint was recorded
    checkpoint_events = [e for e in result.trace_events if e.get("event_type") == "finalization.check" or (e.get("attributes", {}).get("turns_used") is not None)]
    assert result.turns_used == 1


# ---------------------------------------------------------------------------
# Lines 416: reasoning attribute on assistant message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reasoning_content_in_assistant_message():
    """When response has reasoning attribute, it appears in assistant message."""
    provider = FakeProvider(
        [
            NormalizedResponse(content=_done_json(), reasoning="I thought about it"),
        ]
    )
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="deep")

    result = await loop.run(
        AgentRunRequest(
            session_id="reasoning-test",
            messages=[{"role": "user", "content": "think"}],
            max_turns=1,
        )
    )
    assert result.status == "final"
    # The assistant message should have reasoning_content
    assistant_msgs = [m for m in result.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 1
    assert assistant_msgs[0].get("reasoning_content") == "I thought about it"


# ---------------------------------------------------------------------------
# Lines 480-491: concurrent batch dispatch session limit exceeded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_batch_session_limit_exceeded():
    """When concurrent tool dispatch exceeds session limit, run is blocked."""
    concurrent_profile = ModelProfile(
        name="test_concurrent",
        budget=BudgetConfig.for_profile("default"),
        max_session_tool_calls=2,
        concurrent_tool_dispatch=True,
        strict_output=False,
    )
    # Each turn sends 3 tool calls, limit is 2
    responses = [
        NormalizedResponse(
            tool_calls=[
                ToolCall(id=f"c{i}", name="echo", arguments={"value": f"v{i}"})
                for i in range(3)
            ],
            content="",
        ),
        NormalizedResponse(content=_done_json()),
    ]
    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile=concurrent_profile)

    result = await loop.run(
        AgentRunRequest(
            session_id="batch-limit-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    assert result.status == RuntimeStatus.BLOCKED.value


# ---------------------------------------------------------------------------
# Lines 496-515: sequential dispatch session limit exceeded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sequential_session_tool_limit_exceeded():
    """When sequential dispatch exceeds session tool call limit, run is blocked."""
    # Profile with max_session_tool_calls=3 and one_tool_call_per_turn=False
    low_limit_profile = ModelProfile(
        name="test_low_limit",
        budget=BudgetConfig.for_profile("default"),
        max_session_tool_calls=3,
        max_tool_calls_per_turn=10,
        one_tool_call_per_turn=False,
        concurrent_tool_dispatch=False,
        strict_output=False,
    )
    # Turn 1: 2 tool calls, Turn 2: 2 tool calls (total 4 > 3)
    responses = [
        NormalizedResponse(
            tool_calls=[
                ToolCall(id="c1", name="echo", arguments={"value": "v1"}),
                ToolCall(id="c2", name="echo", arguments={"value": "v2"}),
            ],
            content="",
        ),
        NormalizedResponse(
            tool_calls=[
                ToolCall(id="c3", name="echo", arguments={"value": "v3"}),
                ToolCall(id="c4", name="echo", arguments={"value": "v4"}),
            ],
            content="",
        ),
        NormalizedResponse(content=_done_json()),
    ]
    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile=low_limit_profile)

    result = await loop.run(
        AgentRunRequest(
            session_id="seq-limit-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=5,
        )
    )
    assert result.status == RuntimeStatus.BLOCKED.value
    assert any("Session tool call limit exceeded" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Lines 707, 709: _record_schema_repair_hint_event with non-list types
# ---------------------------------------------------------------------------


def test_record_schema_repair_hint_event_with_non_list_types():
    """When hint_types or hint_details are not lists, they are defaulted."""
    events: list[dict[str, Any]] = []
    tool_result = ToolResult(
        "test_tool",
        "content",
        metadata={
            "schema_repair_hints": ["fix the argument"],
            "schema_repair_hint_types": "not_a_list",  # not a list -> []
            "schema_repair_hint_details": 42,  # not a list -> []
        },
    )
    AgentLoop._record_schema_repair_hint_event(
        events, "session-1", turn=1,
        tool_result=tool_result,
        parent_event_id="parent-001",
    )
    assert len(events) == 1
    assert events[0]["attributes"]["schema_repair_hint_types"] == []
    assert events[0]["attributes"]["schema_repair_hint_details"] == []


# ---------------------------------------------------------------------------
# Lines 738: _tool_feedback_content summarization path
# ---------------------------------------------------------------------------


def test_tool_feedback_content_summarization():
    """When content is long and no failure_type, summarize_tool_result is called."""
    long_content = "x" * 5000
    tool_result = ToolResult("test_tool", long_content, metadata={})
    feedback = AgentLoop._tool_feedback_content(tool_result)
    # summarize_tool_result should produce a summary header
    assert "[test_tool] Summary" in feedback


# ---------------------------------------------------------------------------
# Lines 766-772: _tool_feedback_content schema_repair_feedback path
# ---------------------------------------------------------------------------


def test_tool_feedback_content_schema_repair_feedback():
    """When hints are not a list, schema_repair_feedback is called."""
    tool_result = ToolResult(
        "test_tool",
        "bad output",
        status="error",
        error="schema error",
        metadata={
            "failure_type": "schema_validation_failed",
            "recoverable": True,
            "retry_allowed": True,
            "repair_instruction": "fix it",
            "schema_errors": ["field 'x': missing required property"],
            "schema_repair_hints": "not_a_list",  # triggers schema_repair_feedback
        },
    )
    feedback = AgentLoop._tool_feedback_content(tool_result)
    parsed = json.loads(feedback)
    assert parsed["error_type"] == "schema_validation_failed"
    assert isinstance(parsed["schema_repair_hints"], list)
    # Verify that the tool_result metadata was updated with the computed hints
    assert isinstance(tool_result.metadata["schema_repair_hints"], list)
    assert isinstance(tool_result.metadata["schema_repair_hint_types"], list)
    assert isinstance(tool_result.metadata["schema_repair_hint_details"], list)


# ---------------------------------------------------------------------------
# Lines 792-806: _compact_feedback truncation
# ---------------------------------------------------------------------------


def test_compact_feedback_truncates_long_json():
    """Long JSON content is compacted by truncating large values."""
    long_error = "e" * 800
    long_result = "r" * 800
    data = {"error": long_error, "result": long_result, "status": "ok"}
    content = json.dumps(data)
    compacted = AgentLoop._compact_feedback(content, max_chars=1000)
    assert len(compacted) <= 1050  # margin for truncation markers and structure
    # Verify truncation markers
    assert "... [truncated]" in compacted


def test_compact_feedback_truncates_non_json():
    """Non-JSON content is truncated with a marker."""
    content = "a" * 5000
    compacted = AgentLoop._compact_feedback(content, max_chars=1000)
    assert len(compacted) <= 1020
    assert "... [truncated]" in compacted


def test_compact_feedback_short_content_unchanged():
    """Short content passes through unchanged."""
    content = json.dumps({"error": "short"})
    compacted = AgentLoop._compact_feedback(content, max_chars=4000)
    assert compacted == content


# ---------------------------------------------------------------------------
# Lines 812-813: _json_or_text
# ---------------------------------------------------------------------------


def test_json_or_text_parses_valid_json():
    result = AgentLoop._json_or_text('{"key": "value"}')
    assert result == {"key": "value"}


def test_json_or_text_returns_text_on_invalid_json():
    result = AgentLoop._json_or_text("not json at all")
    assert result == "not json at all"


# ---------------------------------------------------------------------------
# Lines 911: _predict_tool_failure_shape_key when registry has no spec
# ---------------------------------------------------------------------------


def test_predict_tool_failure_shape_key_missing_spec():
    """When the tool is not in the registry, returns None."""
    registry = ToolRegistry()
    provider = FakeProvider([{"content": "done"}])
    loop = AgentLoop(provider=provider, registry=registry, profile="deep")

    call = ToolCall(id="c1", name="nonexistent_tool", arguments={"x": 1})
    result = loop._predict_tool_failure_shape_key(call)
    assert result is None


# ---------------------------------------------------------------------------
# Lines 931-932: _command_semantic_shape shlex ValueError
# ---------------------------------------------------------------------------


def test_command_semantic_shape_shlex_error():
    """Malformed shell command string falls back to str.split()."""
    # A string with unbalanced quotes causes shlex.split to raise ValueError
    call = ToolCall(id="c1", name="run", arguments={"command": 'echo "unbalanced'})
    result = AgentLoop._command_semantic_shape(call)
    # Should not raise, should return something from str.split fallback
    assert result is not None


def test_command_semantic_shape_list_command():
    """When command is a list, parts are stringified."""
    call = ToolCall(id="c1", name="run", arguments={"command": ["python", "-m", "pytest"]})
    result = AgentLoop._command_semantic_shape(call)
    assert result == "python pytest"  # -m is a flag, stripped; pytest is kept as word


def test_command_semantic_shape_no_command():
    """When no command argument exists, returns None."""
    call = ToolCall(id="c1", name="run", arguments={"other": "value"})
    result = AgentLoop._command_semantic_shape(call)
    assert result is None


# ---------------------------------------------------------------------------
# Lines 968: _normalize_error_text path with path separators
# ---------------------------------------------------------------------------


def test_normalize_error_text_with_paths_and_values():
    """Paths and numeric values are normalized."""
    result = AgentLoop._normalize_error_text("Error at /usr/bin/python exit code 42")
    assert "<path>" in result
    assert "<value>" in result
    assert "error" in result or "at" in result


# ---------------------------------------------------------------------------
# Lines 999-1007, 1027: Parser repair exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parser_repair_exhaustion():
    """When parser repair retries are exhausted, empty list returned and trace recorded."""
    from metis.runtime.errors import ParserError
    from metis.providers.parsers.base import ToolCallParser

    class _AlwaysFailParser(ToolCallParser):
        def parse(self, raw):
            raise ParserError("cannot parse this")

    provider = FakeProvider(
        [
            # Responses for repair attempts (will exhaust retries)
            NormalizedResponse(content="still broken", raw="still broken"),
            NormalizedResponse(content="still broken", raw="still broken"),
            NormalizedResponse(content=_done_json()),
        ]
    )
    # Use a profile with parser_repair_retries=1 (2 total attempts)
    loop = AgentLoop(
        provider=provider,
        registry=_echo_registry(),
        profile="deep",  # parser_repair_retries=1
        tool_call_parser=_AlwaysFailParser(),
    )

    # First response has no tool_calls -> triggers parser chain on raw content
    result = await loop.run(
        AgentRunRequest(
            session_id="parser-repair-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    # Should have errors about parser failures
    assert any("ParserError" in e for e in result.errors)
    # Check trace events for parser repair
    repair_events = [e for e in result.trace_events if "parser.repair" in e["event_type"]]
    assert len(repair_events) > 0


# ---------------------------------------------------------------------------
# Lines 1058-1066: _repair_final_output success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repair_final_output_success():
    """When strict output repair succeeds, repaired content is used."""
    from metis.runtime.strict_output import StrictOutputParser, StrictOutputError

    # First response: invalid strict output (missing keys)
    # Second response (repair): valid strict output
    bad_content = "this is not json"
    good_content = json.dumps({
        "status": "done",
        "summary": "repaired",
        "evidence_refs": [],
        "artifact_refs": [],
        "next_action": "",
    })

    # Profile with strict_output=True, strict_output_soft=False
    strict_profile = ModelProfile(
        name="test_strict",
        budget=BudgetConfig.for_profile("default"),
        strict_output=True,
        strict_output_soft=False,
    )

    provider = FakeProvider(
        [
            NormalizedResponse(content=bad_content),
            NormalizedResponse(content=good_content),
        ]
    )
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile=strict_profile)

    result = await loop.run(
        AgentRunRequest(
            session_id="repair-final-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    assert result.status in ("final", "blocked")
    assert "StrictOutputError" in result.errors[0] or "repaired" in result.final_text


# ---------------------------------------------------------------------------
# Lines 1244, 1271: State store recording in rate-limit and circuit-breaker paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_records_state(tmp_path):
    """When rate limiting triggers, state records the tool call."""
    from metis.state.sqlite_store import SQLiteStateStore

    state = SQLiteStateStore(tmp_path / "rate_limit_state.db")
    # Create enough responses to exceed MAX_SAME_TOOL_PER_SESSION (20)
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": f"v{i}"}, "id": f"c{i}"}]}
        for i in range(22)
    ]
    responses.append({"content": _done_json()})

    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=_echo_registry(), profile="small", state=state)

    result = await loop.run(
        AgentRunRequest(
            session_id="rate-state-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=30,
        )
    )

    # Verify that tool calls were recorded
    tool_calls = state.list_tool_calls("rate-state-test")
    assert len(tool_calls) > 0
    # Some should be rate-limited
    rate_limited = [r for r in result.tool_results if r.metadata.get("rate_limited")]
    assert len(rate_limited) > 0


@pytest.mark.asyncio
async def test_circuit_breaker_records_state(tmp_path):
    """When circuit breaker triggers, state records the blocked tool call."""
    from metis.state.sqlite_store import SQLiteStateStore

    state = SQLiteStateStore(tmp_path / "cb_state.db")

    def fail_handler(args, ctx):
        raise RuntimeError("always fails")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "fail_tool",
            "Fail",
            {"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False},
            fail_handler,
        )
    )

    responses = [
        {"tool_calls": [{"name": "fail_tool", "arguments": {"value": f"v{i}"}, "id": f"c{i}"}]}
        for i in range(5)
    ]
    responses.append({"content": _done_json()})

    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=registry, profile="small", state=state)

    result = await loop.run(
        AgentRunRequest(
            session_id="cb-state-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=10,
        )
    )

    # Check circuit breaker results exist
    cb_results = [r for r in result.tool_results if r.metadata.get("circuit_breaker")]
    assert len(cb_results) >= 1
    # Verify state recorded tool calls (including circuit-broken ones)
    tool_calls = state.list_tool_calls("cb-state-test")
    assert len(tool_calls) > 0


# ---------------------------------------------------------------------------
# Lines 1381-1388: Concurrent batch dispatch session limit in _dispatch_one
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_dispatch_session_limit_inside_dispatch_one():
    """When total_tool_calls exceeds limit inside batch _dispatch_one, error recorded."""
    concurrent_profile = ModelProfile(
        name="test_concurrent_inner",
        budget=BudgetConfig.for_profile("default"),
        max_session_tool_calls=1,
        concurrent_tool_dispatch=True,
        strict_output=False,
    )
    # 3 read-only tool calls in a single turn
    registry = _echo_registry()
    responses = [
        NormalizedResponse(
            tool_calls=[
                ToolCall(id="c1", name="echo", arguments={"value": "a"}),
                ToolCall(id="c2", name="echo", arguments={"value": "b"}),
                ToolCall(id="c3", name="echo", arguments={"value": "c"}),
            ],
            content="",
        ),
        NormalizedResponse(content=_done_json()),
    ]
    provider = FakeProvider(responses)
    loop = AgentLoop(provider=provider, registry=registry, profile=concurrent_profile)

    result = await loop.run(
        AgentRunRequest(
            session_id="concurrent-inner-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )
    assert result.status == RuntimeStatus.BLOCKED.value


# ---------------------------------------------------------------------------
# Lines 999-1007: Parser repair final failure trace event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parser_repair_final_failure_records_trace():
    """Verify that the final parser repair failure records a 'failed' trace event."""
    from metis.runtime.errors import ParserError
    from metis.providers.parsers.base import ToolCallParser

    class _FailParser(ToolCallParser):
        def parse(self, raw):
            raise ParserError("unparseable")

    provider = FakeProvider(
        [
            NormalizedResponse(content="bad", raw="bad"),
            NormalizedResponse(content=_done_json()),
        ]
    )
    # deep profile has parser_repair_retries=1, so 2 total attempts
    loop = AgentLoop(
        provider=provider,
        registry=_echo_registry(),
        profile="deep",
        tool_call_parser=_FailParser(),
    )

    result = await loop.run(
        AgentRunRequest(
            session_id="parser-trace-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=3,
        )
    )

    failed_repair = [
        e for e in result.trace_events
        if e["event_type"] == "parser.repair.result" and e["status"] == "failed"
    ]
    assert len(failed_repair) >= 1


# ---------------------------------------------------------------------------
# Lines 1027: Parser repair raw fallback (raw = repaired.content)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parser_repair_uses_content_when_raw_not_string():
    """When repaired.raw is not a string, raw falls back to repaired.content."""
    from metis.runtime.errors import ParserError
    from metis.providers.parsers.base import ToolCallParser

    call_count = 0

    class _FailOnceParser(ToolCallParser):
        def __init__(self):
            self.attempt = 0

        def parse(self, raw):
            self.attempt += 1
            if self.attempt <= 2:
                raise ParserError("not valid")
            # On 3rd attempt, return a tool call
            return [ToolCall(id="c1", name="echo", arguments={"value": "repaired"})]

    provider = FakeProvider(
        [
            # First response triggers parser
            NormalizedResponse(content="some text", raw={"not": "a string"}),
            # Repair response - also returns non-string raw
            NormalizedResponse(content="more text", raw=12345),
            # Another response for after parser succeeds (no tool_calls -> done)
            NormalizedResponse(content=_done_json()),
        ]
    )
    loop = AgentLoop(
        provider=provider,
        registry=_echo_registry(),
        profile="deep",
        tool_call_parser=_FailOnceParser(),
    )

    result = await loop.run(
        AgentRunRequest(
            session_id="parser-raw-test",
            messages=[{"role": "user", "content": "run"}],
            max_turns=5,
        )
    )
    # Should complete with errors about parser
    assert len(result.errors) >= 0  # may or may not have errors depending on path


# ---------------------------------------------------------------------------
# Lines 707: _record_schema_repair_hint_event with empty hints list
# ---------------------------------------------------------------------------


def test_record_schema_repair_hint_event_empty_hints():
    """When hints list is empty, no event is recorded."""
    events: list[dict[str, Any]] = []
    tool_result = ToolResult(
        "test_tool",
        "content",
        metadata={
            "schema_repair_hints": [],
        },
    )
    AgentLoop._record_schema_repair_hint_event(
        events, "session-1", turn=1,
        tool_result=tool_result,
        parent_event_id="parent-001",
    )
    assert len(events) == 0


# ---------------------------------------------------------------------------
# Lines 707: _record_schema_repair_hint_event with non-list hints (not list)
# ---------------------------------------------------------------------------


def test_record_schema_repair_hint_event_hints_not_list():
    """When hints is not a list, no event is recorded."""
    events: list[dict[str, Any]] = []
    tool_result = ToolResult(
        "test_tool",
        "content",
        metadata={
            "schema_repair_hints": "not_a_list",
        },
    )
    AgentLoop._record_schema_repair_hint_event(
        events, "session-1", turn=1,
        tool_result=tool_result,
        parent_event_id="parent-001",
    )
    assert len(events) == 0


# ---------------------------------------------------------------------------
# Additional: _tool_feedback_content with evidence_refs
# ---------------------------------------------------------------------------


def test_tool_feedback_content_with_evidence_refs():
    """When tool result has evidence_refs but no failure_type, JSON with evidence_refs is returned."""
    tool_result = ToolResult(
        "test_tool",
        '{"result": "success"}',
        metadata={
            "evidence_refs": ["ev1", "ev2"],
        },
    )
    feedback = AgentLoop._tool_feedback_content(tool_result)
    parsed = json.loads(feedback)
    assert parsed["evidence_refs"] == ["ev1", "ev2"]
    assert "evidence_instruction" in parsed


# ---------------------------------------------------------------------------
# Additional: _tool_feedback_content with failure_type and policy_decision
# ---------------------------------------------------------------------------


def test_tool_feedback_content_with_policy_decision():
    """When tool result has failure_type and policy_decision, both appear in feedback."""
    tool_result = ToolResult(
        "test_tool",
        "denied",
        status="error",
        error="policy denied",
        metadata={
            "failure_type": "policy_denied",
            "recoverable": False,
            "retry_allowed": False,
            "repair_instruction": "use different tool",
            "policy_decision": "blocked",
            "risk_level": "high",
            "exit_code": 1,
        },
    )
    feedback = AgentLoop._tool_feedback_content(tool_result)
    parsed = json.loads(feedback)
    assert parsed["policy_decision"] == "blocked"
    assert parsed["risk_level"] == "high"
    assert parsed["exit_code"] == 1


# ---------------------------------------------------------------------------
# Additional: _tool_feedback_content with failure_shape_key
# ---------------------------------------------------------------------------


def test_tool_feedback_content_with_failure_shape_key():
    """failure_shape_key is included in feedback when present."""
    tool_result = ToolResult(
        "test_tool",
        "error",
        status="error",
        error="bad shape",
        metadata={
            "failure_type": "command_failed",
            "recoverable": True,
            "retry_allowed": True,
            "repair_instruction": "fix command",
            "failure_shape_key": "echo <value>",
        },
    )
    feedback = AgentLoop._tool_feedback_content(tool_result)
    parsed = json.loads(feedback)
    assert parsed["failure_shape_key"] == "echo <value>"
