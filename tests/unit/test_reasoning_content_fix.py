"""Tests for reasoning_content fix on thinking-enabled models."""

from __future__ import annotations

import pytest

from metis.providers.base import BaseProvider, NormalizedResponse, ProviderCapabilities
from metis.runtime.loop import AgentLoop
from metis.runtime.response import ToolCall
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeProviderWithToolCall(BaseProvider):
    def __init__(self, responses, thinking=True):
        self.responses = list(responses)
        self._index = 0
        self.model = "glm-4.7-flash"
        self.last_messages = []
        self._thinking = thinking

    async def complete(self, messages, tools=None, **params):
        self.last_messages = messages
        resp = self.responses[self._index]
        self._index += 1
        tool_calls = []
        for tc in resp.get("tool_calls", []):
            tool_calls.append(ToolCall(id=tc.get("id", "c"), name=tc["name"], arguments=tc["arguments"]))
        return NormalizedResponse(
            content=resp.get("content", ""),
            tool_calls=tool_calls,
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type="test", model=self.model, thinking=self._thinking
        )


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda a, c: {"v": "ok"}))
    return registry


@pytest.mark.asyncio
async def test_assistant_message_gets_reasoning_content_on_tool_call():
    provider = FakeProviderWithToolCall([
        {"content": "ok", "tool_calls": [{"id": "c1", "name": "echo", "arguments": {}}]},
        {"content": "done"},
    ], thinking=True)
    loop = AgentLoop(
        provider=provider,
        registry=_registry(),
        profile="deep",
    )
    from metis.runtime.response import AgentRunRequest
    result = await loop.run(AgentRunRequest(
        session_id="reasoning-fix",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    assistant_msgs = [m for m in result.messages if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 1
    tool_call_msg = [m for m in assistant_msgs if "tool_calls" in m][0]
    assert "reasoning_content" in tool_call_msg


@pytest.mark.asyncio
async def test_provider_messages_sanitized_for_thinking_model():
    provider = FakeProviderWithToolCall([
        {"content": "ok", "tool_calls": [{"id": "c1", "name": "echo", "arguments": {}}]},
        {"content": "done"},
    ], thinking=True)
    loop = AgentLoop(
        provider=provider,
        registry=_registry(),
        profile="deep",
    )
    from metis.runtime.response import AgentRunRequest
    await loop.run(AgentRunRequest(
        session_id="sanitize-test",
        messages=[{"role": "user", "content": "hi"}],
        max_turns=5,
    ))
    second_turn_msgs = provider.last_messages
    assistant_with_tools = [m for m in second_turn_msgs if m.get("role") == "assistant" and "tool_calls" in m]
    for msg in assistant_with_tools:
        assert "reasoning_content" in msg


def test_ensure_reasoning_content_skips_non_thinking_models():
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "echo"}}]},
    ]
    result = AgentLoop._ensure_reasoning_content(messages, thinking_enabled=False)
    assert "reasoning_content" not in result[0]


def test_ensure_reasoning_content_adds_for_thinking_enabled():
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "echo"}}]},
    ]
    result = AgentLoop._ensure_reasoning_content(messages, thinking_enabled=True)
    assert result[0].get("reasoning_content") == ""


def test_ensure_reasoning_content_preserves_existing():
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}], "reasoning_content": "think"},
    ]
    result = AgentLoop._ensure_reasoning_content(messages, thinking_enabled=True)
    assert result[0].get("reasoning_content") == "think"
