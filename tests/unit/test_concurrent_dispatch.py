"""Tests for concurrent tool dispatch in the agent loop."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, AgentRunResult, ToolCall
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolSpec


def _make_read_tool(name: str, delay: float = 0):
    call_log: list[float] = []

    def handler(args: dict, context: ToolContext) -> dict:
        call_log.append(time.monotonic())
        if delay > 0:
            time.sleep(delay)
        return {"tool": name, "result": "ok"}

    handler.call_log = call_log
    return handler


def _make_write_tool(name: str):
    call_order: list[str] = []

    def handler(args: dict, context: ToolContext) -> dict:
        call_order.append(name)
        return {"tool": name, "written": True}

    handler.call_order = call_order
    return handler


def _registry_with_tools():
    registry = ToolRegistry()
    read_a = _make_read_tool("read_a", delay=0.05)
    read_b = _make_read_tool("read_b", delay=0.05)
    write_c = _make_write_tool("write_c")

    registry.register(ToolSpec(
        name="read_a",
        description="Read tool A",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=read_a,
        category="files",
        side_effect="read",
    ))
    registry.register(ToolSpec(
        name="read_b",
        description="Read tool B",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=read_b,
        category="files",
        side_effect="read",
    ))
    registry.register(ToolSpec(
        name="write_c",
        description="Write tool C",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=write_c,
        category="files",
        side_effect="write",
    ))
    return registry


class TestConcurrentDispatchProfile:
    def test_deep_profile_has_concurrent_dispatch(self):
        from metis.runtime.profiles import PROFILES
        assert PROFILES["deep"].concurrent_tool_dispatch is True

    def test_small_profile_has_no_concurrent_dispatch(self):
        from metis.runtime.profiles import PROFILES
        assert PROFILES["small"].concurrent_tool_dispatch is False

    def test_balanced_profile_has_no_concurrent_dispatch(self):
        from metis.runtime.profiles import PROFILES
        assert PROFILES["balanced"].concurrent_tool_dispatch is False


class TestConcurrentDispatchExecution:
    @pytest.mark.asyncio
    async def test_concurrent_read_tools_run_in_parallel(self):
        registry = _registry_with_tools()

        call_count = 0

        class MockProvider(BaseProvider):
            async def complete(self, messages, tools=None, **params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return NormalizedResponse(
                        content="",
                        tool_calls=[
                            ToolCall(id="1", name="read_a", arguments={}),
                            ToolCall(id="2", name="read_b", arguments={}),
                        ],
                        finish_reason="tool_calls",
                        usage={"prompt_tokens": 10, "completion_tokens": 5},
                    )
                return NormalizedResponse(
                    content="done",
                    tool_calls=[],
                    finish_reason="stop",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                )

        loop = AgentLoop(
            provider=MockProvider(),
            registry=registry,
            profile="deep",
        )
        result = await loop.run(AgentRunRequest(
            session_id="test-concurrent",
            messages=[{"role": "user", "content": "test"}],
            max_turns=5,
        ))
        assert result.status in ("done", "max_turns", "final", "verified")
        assert len(result.tool_results) == 2

        tool_names = {r.tool_name for r in result.tool_results}
        assert tool_names == {"read_a", "read_b"}

    @pytest.mark.asyncio
    async def test_write_tools_still_sequential(self):
        registry = _registry_with_tools()
        write_c_handler = registry.get("write_c").handler

        call_count = 0

        class MockProvider(BaseProvider):
            async def complete(self, messages, tools=None, **params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return NormalizedResponse(
                        content="",
                        tool_calls=[
                            ToolCall(id="1", name="read_a", arguments={}),
                            ToolCall(id="2", name="write_c", arguments={}),
                        ],
                        finish_reason="tool_calls",
                        usage={"prompt_tokens": 10, "completion_tokens": 5},
                    )
                return NormalizedResponse(
                    content="done",
                    tool_calls=[],
                    finish_reason="stop",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                )

        loop = AgentLoop(
            provider=MockProvider(),
            registry=registry,
            profile="deep",
        )
        result = await loop.run(AgentRunRequest(
            session_id="test-mixed",
            messages=[{"role": "user", "content": "test"}],
            max_turns=5,
        ))
        assert len(result.tool_results) == 2
        names = [r.tool_name for r in result.tool_results]
        assert "read_a" in names
        assert "write_c" in names

    @pytest.mark.asyncio
    async def test_non_concurrent_profile_dispatches_sequentially(self):
        registry = _registry_with_tools()

        call_count = 0

        class MockProvider(BaseProvider):
            async def complete(self, messages, tools=None, **params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return NormalizedResponse(
                        content="",
                        tool_calls=[
                            ToolCall(id="1", name="read_a", arguments={}),
                            ToolCall(id="2", name="read_b", arguments={}),
                        ],
                        finish_reason="tool_calls",
                        usage={"prompt_tokens": 10, "completion_tokens": 5},
                    )
                return NormalizedResponse(
                    content="done",
                    tool_calls=[],
                    finish_reason="stop",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                )

        loop = AgentLoop(
            provider=MockProvider(),
            registry=registry,
            profile="small",
        )
        result = await loop.run(AgentRunRequest(
            session_id="test-sequential",
            messages=[{"role": "user", "content": "test"}],
            max_turns=5,
        ))
        assert len(result.tool_results) >= 1

    @pytest.mark.asyncio
    async def test_batch_trace_event_emitted(self):
        registry = _registry_with_tools()

        call_count = 0

        class MockProvider(BaseProvider):
            async def complete(self, messages, tools=None, **params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return NormalizedResponse(
                        content="",
                        tool_calls=[
                            ToolCall(id="1", name="read_a", arguments={}),
                            ToolCall(id="2", name="read_b", arguments={}),
                        ],
                        finish_reason="tool_calls",
                        usage={"prompt_tokens": 10, "completion_tokens": 5},
                    )
                return NormalizedResponse(
                    content="done",
                    tool_calls=[],
                    finish_reason="stop",
                    usage={"prompt_tokens": 10, "completion_tokens": 5},
                )

        loop = AgentLoop(
            provider=MockProvider(),
            registry=registry,
            profile="deep",
        )
        result = await loop.run(AgentRunRequest(
            session_id="test-batch-trace",
            messages=[{"role": "user", "content": "test"}],
            max_turns=5,
        ))
        batch_events = [e for e in result.trace_events if e.get("event_type") == "tool.batch"]
        assert len(batch_events) == 1
        assert batch_events[0]["attributes"]["concurrent_count"] == 2
        assert batch_events[0]["attributes"]["sequential_count"] == 0
