"""Tests for provider streaming (SSE parsing)."""

import json

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.errors import ProviderError
from metis.runtime.response import StreamChunk


@pytest.mark.asyncio
async def test_complete_stream_yields_chunks(monkeypatch):
    """complete_stream parses SSE chunks and yields StreamChunk objects."""
    chunks = []

    async def mock_handler(request):
        body = json.loads(request.content)
        assert body.get("stream") is True
        lines = [
            'data: ' + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            'data: ' + json.dumps({"choices": [{"delta": {"content": " world"}}]}),
            'data: [DONE]',
        ]
        content = "\n".join(lines) + "\n"
        return httpx.Response(200, content=content, headers={"content-type": "text/event-stream"})

    import httpx
    provider = OpenAICompatibleProvider(
        base_url="https://stream.test/v1",
        api_key="key",
        model="gpt-4o",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider._client = client
        async for chunk in provider.complete_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

    assert len(chunks) >= 2
    content_parts = [c.content for c in chunks if not c.is_finished]
    assert "Hello" in content_parts or any("Hello" in c.content for c in chunks)
    final = [c for c in chunks if c.is_finished]
    assert len(final) == 1
    assert final[0].content == "Hello world"


@pytest.mark.asyncio
async def test_complete_stream_with_tool_calls(monkeypatch):
    """complete_stream handles tool call deltas spread across chunks."""
    chunks = []

    async def mock_handler(request):
        lines = [
            'data: ' + json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "read_"}}]}}]}),
            'data: ' + json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "file", "arguments": '{"path": "' }}]}}]}),
            'data: ' + json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'test.txt"}'}}]}}]}),
            'data: [DONE]',
        ]
        content = "\n".join(lines) + "\n"
        return httpx.Response(200, content=content, headers={"content-type": "text/event-stream"})

    import httpx
    provider = OpenAICompatibleProvider(
        base_url="https://stream.test/v1",
        api_key="key",
        model="gpt-4o",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider._client = client
        async for chunk in provider.complete_stream([{"role": "user", "content": "read test.txt"}]):
            chunks.append(chunk)

    final = [c for c in chunks if c.is_finished]
    assert len(final) == 1
    assert len(final[0].tool_calls or []) == 1
    assert final[0].tool_calls[0].name == "read_file"


@pytest.mark.asyncio
async def test_complete_stream_raises_on_http_error(monkeypatch):
    """complete_stream raises ProviderError on HTTP error."""
    async def mock_handler(request):
        return httpx.Response(500, json={"error": "internal"})

    import httpx
    provider = OpenAICompatibleProvider(
        base_url="https://stream.test/v1",
        api_key="key",
        model="gpt-4o",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider._client = client
        with pytest.raises(ProviderError, match="Streaming request failed"):
            async for _ in provider.complete_stream([{"role": "user", "content": "hi"}]):
                pass


def test_openai_compat_detects_streaming_capability():
    """Known models report streaming=True in capabilities."""
    provider = OpenAICompatibleProvider(
        base_url="https://test/v1", api_key="key", model="gpt-4o"
    )
    caps = provider.capabilities()
    assert caps.streaming is True


def test_openai_compat_unknown_model_defaults_streaming_false():
    """Unknown models default to streaming=False."""
    provider = OpenAICompatibleProvider(
        base_url="https://test/v1", api_key="key", model="unknown-model-v99"
    )
    caps = provider.capabilities()
    assert caps.streaming is False
