"""Tests for dynamic temperature adjustment."""

from __future__ import annotations

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse, ProviderCapabilities
from metis.runtime.loop import AgentLoop
from metis.runtime.response import ToolCall
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProviderWithParams(BaseProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self._index = 0
        self.model = "test-model-v1"
        self.last_params = {}

    async def complete(self, messages, tools=None, **params):
        self.last_params = params
        resp = self.responses[self._index]
        self._index += 1
        tool_calls = []
        for tc in resp.get("tool_calls", []):
            tool_calls.append(ToolCall(id=tc.get("id", "c"), name=tc["name"], arguments=tc["arguments"]))
        return NormalizedResponse(content=resp.get("content", ""), tool_calls=tool_calls)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type="test", model=self.model)


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda a, c: {"v": "ok"}))
    return registry


def test_temperature_base_on_first_turn():
    temp = AgentLoop._compute_temperature(0, {}, [])
    assert temp == 0.2


def test_temperature_increases_with_turn_index():
    assert AgentLoop._compute_temperature(1, {}, []) == 0.25
    assert AgentLoop._compute_temperature(2, {}, []) == 0.3
    assert AgentLoop._compute_temperature(4, {}, []) == 0.4


def test_temperature_turn_boost_capped():
    assert AgentLoop._compute_temperature(10, {}, []) == 0.55


def test_temperature_increases_with_repair_failures():
    repairs = {("echo", "schema_error"): 1}
    assert AgentLoop._compute_temperature(0, repairs, []) == 0.3


def test_temperature_increases_with_loop_risk():
    sigs = ["text:hello", "text:hello"]
    assert AgentLoop._compute_temperature(0, {}, sigs) == 0.35


def test_temperature_combined_boosts():
    repairs = {("echo", "error"): 2}
    sigs = ["a", "a"]
    assert AgentLoop._compute_temperature(2, repairs, sigs) == 0.55


def test_temperature_clamped_maximum():
    repairs = {("echo", "error"): 10}
    sigs = ["a", "a"]
    # 0.2 base + 0.35 turn boost + 0.1 repair + 0.15 loop = 0.8
    assert AgentLoop._compute_temperature(30, repairs, sigs) == 0.8


def test_temperature_no_loop_boost_with_single_signature():
    sigs = ["text:hello"]
    assert AgentLoop._compute_temperature(0, {}, sigs) == 0.2


def test_temperature_no_loop_boost_with_different_signatures():
    sigs = ["text:hello", "text:world"]
    assert AgentLoop._compute_temperature(0, {}, sigs) == 0.2


@pytest.mark.asyncio
async def test_provider_receives_dynamic_temperature():
    provider = FakeProviderWithParams([{"content": "done"}])
    loop = AgentLoop(
        provider=provider,
        registry=_registry(),
        profile="small",
    )
    from metis.runtime.response import AgentRunRequest
    result = await loop.run(AgentRunRequest(
        session_id="temp-test",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    assert provider.last_params.get("temperature") == 0.2
    request_events = [e for e in result.trace_events if e["event_type"] == "model.request"]
    assert request_events[0]["attributes"]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_temperature_increases_on_second_turn():
    # First turn triggers a tool call, second turn returns final text
    provider = FakeProviderWithParams([
        {"content": "ok", "tool_calls": [{"id": "c1", "name": "echo", "arguments": {}}]},
        {"content": "done"},
    ])
    loop = AgentLoop(
        provider=provider,
        registry=_registry(),
        profile="deep",
    )
    from metis.runtime.response import AgentRunRequest
    result = await loop.run(AgentRunRequest(
        session_id="temp-turn2",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    request_events = [e for e in result.trace_events if e["event_type"] == "model.request"]
    assert len(request_events) == 2
    assert request_events[0]["attributes"]["temperature"] == 0.2
    assert request_events[1]["attributes"]["temperature"] == 0.25
