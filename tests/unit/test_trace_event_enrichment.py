"""Tests for enriched trace events in AgentLoop."""

from __future__ import annotations

import pytest

from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.providers.base import BaseProvider, NormalizedResponse
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProvider(BaseProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0
        self.model = "test-model-v1"

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        return NormalizedResponse(content=resp.get("content", ""))


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda a, c: {"v": "ok"}))
    return registry


@pytest.mark.asyncio
async def test_model_request_trace_includes_metadata():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}]),
        registry=_registry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="trace-meta",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    request_events = [e for e in result.trace_events if e["event_type"] == "model.request"]
    assert len(request_events) == 1
    attrs = request_events[0]["attributes"]
    assert attrs["model"] == "test-model-v1"
    assert "estimated_tokens" in attrs
    assert "max_chars_budget" in attrs
    assert "compression_ratio" in attrs
    assert attrs["message_count"] == 1


@pytest.mark.asyncio
async def test_compression_ratio_recorded_when_compressed():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}]),
        registry=_registry(),
        profile="small",
    )
    # Create a long message that triggers compression
    long_msg = "x" * 100_000
    result = await loop.run(AgentRunRequest(
        session_id="trace-compress",
        messages=[{"role": "user", "content": long_msg}],
        max_turns=5,
    ))
    request_events = [e for e in result.trace_events if e["event_type"] == "model.request"]
    assert len(request_events) >= 1
    attrs = request_events[0]["attributes"]
    if attrs.get("compressed"):
        assert attrs["compression_ratio"] > 1.0
