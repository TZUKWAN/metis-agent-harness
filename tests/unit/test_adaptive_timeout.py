"""Tests for adaptive per-turn timeout based on model capabilities."""

from __future__ import annotations

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse, ProviderCapabilities
from metis.runtime.loop import AgentLoop
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProviderWithCaps(BaseProvider):
    def __init__(self, responses, max_output_tokens: int = 0):
        self.responses = list(responses)
        self._index = 0
        self.model = "test-model-v1"
        self._max_output_tokens = max_output_tokens

    async def complete(self, messages, tools=None, **params):
        resp = self.responses[self._index]
        self._index += 1
        return NormalizedResponse(content=resp.get("content", ""))

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type="test",
            model=self.model,
            max_context_tokens=128_000,
            max_output_tokens=self._max_output_tokens,
        )


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda a, c: {"v": "ok"}))
    return registry


def test_timeout_defaults_when_no_capabilities():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=0),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 120


def test_timeout_for_4k_model():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=4096),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 190


def test_timeout_for_8k_model():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=8192),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 290


def test_timeout_for_16k_model():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=16384),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 490


def test_timeout_clamped_at_maximum():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=32768),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 600


def test_timeout_clamped_at_minimum():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=512),
        registry=_registry(),
        profile="small",
    )
    assert loop.per_turn_timeout == 120


@pytest.mark.asyncio
async def test_trace_event_includes_timeout():
    loop = AgentLoop(
        provider=FakeProviderWithCaps([{"content": "done"}], max_output_tokens=8192),
        registry=_registry(),
        profile="small",
    )
    from metis.runtime.response import AgentRunRequest
    result = await loop.run(AgentRunRequest(
        session_id="timeout-trace",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    request_events = [e for e in result.trace_events if e["event_type"] == "model.request"]
    assert len(request_events) == 1
    assert request_events[0]["attributes"]["per_turn_timeout"] == 290
