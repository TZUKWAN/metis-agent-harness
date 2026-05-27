"""Tests verifying AgentLoop uses streaming path when provider supports it."""

import pytest

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, NormalizedResponse, StreamChunk, ToolCall
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeStreamingProvider:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def capabilities(self):
        from metis.providers.base import ProviderCapabilities
        return ProviderCapabilities(
            provider_type="fake_stream", model="fake", streaming=True
        )

    async def complete(self, messages, tools=None, **params):
        content = "".join(c.content for c in self._chunks if not c.is_finished)
        return NormalizedResponse(content=content)

    async def complete_stream(self, messages, tools=None, **params):
        for chunk in self._chunks:
            yield chunk


class FakeNonStreamingProvider:
    def __init__(self, response_text="done"):
        self._text = response_text

    def capabilities(self):
        from metis.providers.base import ProviderCapabilities
        return ProviderCapabilities(
            provider_type="fake", model="fake", streaming=False
        )

    async def complete(self, messages, tools=None, **params):
        return NormalizedResponse(content=self._text)


@pytest.mark.asyncio
async def test_loop_emits_stream_chunk_events_when_provider_supports_streaming():
    """When provider has streaming=True, AgentLoop emits MODEL_STREAM_CHUNK events."""
    registry = ToolRegistry()
    chunks = [
        StreamChunk(content="Hello ", is_finished=False),
        StreamChunk(content="world", is_finished=False),
        StreamChunk(content="Hello world", is_finished=True),
    ]
    provider = FakeStreamingProvider(chunks)
    hooks = HookBus()
    stream_events = []
    hooks.register(EventType.MODEL_STREAM_CHUNK, lambda d: stream_events.append(d))

    loop = AgentLoop(provider=provider, registry=registry, profile="small", hooks=hooks)
    result = await loop.run(AgentRunRequest(session_id="stream-test", messages=[{"role": "user", "content": "hi"}]))

    assert len(stream_events) >= 2
    contents = [e.get("content", "") for e in stream_events]
    assert "Hello " in contents
    assert "world" in contents
    assert result.final_text == "Hello world"


@pytest.mark.asyncio
async def test_loop_uses_complete_when_provider_does_not_support_streaming():
    """When provider has streaming=False, AgentLoop uses non-streaming complete()."""
    registry = ToolRegistry()
    provider = FakeNonStreamingProvider("non-streamed response")
    hooks = HookBus()
    stream_events = []
    hooks.register(EventType.MODEL_STREAM_CHUNK, lambda d: stream_events.append(d))

    loop = AgentLoop(provider=provider, registry=registry, profile="small", hooks=hooks)
    result = await loop.run(AgentRunRequest(session_id="no-stream-test", messages=[{"role": "user", "content": "hi"}]))

    assert len(stream_events) == 0
    assert result.final_text == "non-streamed response"


@pytest.mark.asyncio
async def test_loop_streaming_with_tool_calls():
    """Streaming provider that emits tool calls in final chunk works correctly."""
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"]}, lambda a, c: {"v": a["v"]}))

    chunks = [
        StreamChunk(content="Let me ", is_finished=False),
        StreamChunk(content="use a tool.", is_finished=False),
        StreamChunk(
            content="Let me use a tool.",
            tool_calls=[ToolCall(name="echo", arguments={"v": "test"}, id="c1")],
            is_finished=True,
        ),
    ]
    provider = FakeStreamingProvider(chunks)
    hooks = HookBus()
    stream_events = []
    hooks.register(EventType.MODEL_STREAM_CHUNK, lambda d: stream_events.append(d))

    loop = AgentLoop(provider=provider, registry=registry, profile="small", hooks=hooks)
    result = await loop.run(AgentRunRequest(session_id="stream-tool-test", messages=[{"role": "user", "content": "echo test"}], max_turns=2))

    assert len(stream_events) >= 2
    # Tool should have been dispatched at least once
    assert len(result.tool_results) >= 1
    assert any(r.tool_name == "echo" for r in result.tool_results)
