"""Tests for provider HTTP client lifecycle."""

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_persistent_client_reuse():
    provider = OpenAICompatibleProvider(base_url="https://httpbin.org", api_key="test")
    c1 = provider._get_client()
    c2 = provider._get_client()
    assert c1 is c2
    await provider.close()
    assert provider._client is None


@pytest.mark.asyncio
async def test_close_idempotent():
    provider = OpenAICompatibleProvider(base_url="https://httpbin.org", api_key="test")
    provider._get_client()
    await provider.close()
    await provider.close()
    assert provider._client is None


@pytest.mark.asyncio
async def test_context_manager():
    async with OpenAICompatibleProvider(base_url="https://httpbin.org", api_key="test") as provider:
        assert provider._get_client() is not None
    assert provider._client is None


@pytest.mark.asyncio
async def test_client_recreated_after_close():
    provider = OpenAICompatibleProvider(base_url="https://httpbin.org", api_key="test")
    c1 = provider._get_client()
    await provider.close()
    c2 = provider._get_client()
    assert c1 is not c2
    await provider.close()
