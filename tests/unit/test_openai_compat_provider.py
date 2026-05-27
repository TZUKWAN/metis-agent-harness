import httpx
import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.errors import ProviderError


def test_openai_compat_provider_reports_configured_capabilities(monkeypatch):
    monkeypatch.setenv("METIS_PROVIDER_JSON_SCHEMA_SUPPORTED", "true")
    monkeypatch.setenv("METIS_PROVIDER_MAX_CONTEXT_TOKENS", "131072")
    monkeypatch.setenv("METIS_PROVIDER_MAX_OUTPUT_TOKENS", "65536")
    provider = OpenAICompatibleProvider(base_url="https://example.test/v1", api_key="key", model="glm-4.7-flash")

    capabilities = provider.capabilities().to_dict()

    assert capabilities["provider_type"] == "openai_compatible"
    assert capabilities["model"] == "glm-4.7-flash"
    assert capabilities["native_tool_calling"] is True
    assert capabilities["json_schema_output"] is True
    assert capabilities["thinking"] is True
    assert capabilities["streaming"] is True
    assert capabilities["max_context_tokens"] == 131072
    assert capabilities["max_output_tokens"] == 65536
    assert capabilities["retryable_status_codes"] == [429, 500, 502, 503, 504]


@pytest.mark.asyncio
async def test_openai_compat_provider_retries_429_then_succeeds(monkeypatch):
    calls = {"count": 0}

    async def handler(request):
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": "rate limited"}, headers={"retry-after": "0"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="key",
        max_retries=1,
        retry_backoff_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        data = await provider._post_with_retries(client, "https://example.test/v1/chat/completions", {}, {})

    assert calls["count"] == 2
    assert data["choices"][0]["message"]["content"] == "ok"


@pytest.mark.asyncio
async def test_openai_compat_provider_does_not_retry_non_retryable_400():
    calls = {"count": 0}

    async def handler(request):
        calls["count"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1",
        api_key="key",
        max_retries=3,
        retry_backoff_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError):
            await provider._post_with_retries(client, "https://example.test/v1/chat/completions", {}, {})

    assert calls["count"] == 1
