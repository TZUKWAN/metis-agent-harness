"""Tests for request_id propagation."""

from __future__ import annotations

import pytest

from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.providers.base import BaseProvider, NormalizedResponse
from metis.tools.registry import ToolRegistry


class FakeProvider(BaseProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        return NormalizedResponse(**resp)


@pytest.mark.asyncio
async def test_request_id_in_trace_events():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}]),
        registry=ToolRegistry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-req-id",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
        request_id="req-12345",
    ))
    start_event = [e for e in result.trace_events if e["event_type"] == "agent.start"][0]
    assert start_event["attributes"]["request_id"] == "req-12345"


@pytest.mark.asyncio
async def test_request_id_defaults_to_empty():
    loop = AgentLoop(
        provider=FakeProvider([{"content": "done"}]),
        registry=ToolRegistry(),
        profile="small",
    )
    result = await loop.run(AgentRunRequest(
        session_id="test-req-id-2",
        messages=[{"role": "user", "content": "test"}],
        max_turns=5,
    ))
    start_event = [e for e in result.trace_events if e["event_type"] == "agent.start"][0]
    assert start_event["attributes"]["request_id"] == ""
