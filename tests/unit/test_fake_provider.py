import pytest

from metis.providers.fake import FakeProvider


def test_fake_provider_reports_capabilities():
    capabilities = FakeProvider([]).capabilities().to_dict()

    assert capabilities["provider_type"] == "fake"
    assert capabilities["model"] == "fake"
    assert capabilities["native_tool_calling"] is True
    assert capabilities["json_schema_output"] is True
    assert capabilities["thinking"] is False


@pytest.mark.asyncio
async def test_fake_provider_returns_responses():
    provider = FakeProvider([{"content": "done", "usage": {"total_tokens": 3}}])

    response = await provider.complete([{"role": "user", "content": "hi"}])

    assert response.content == "done"
    assert response.usage == {"total_tokens": 3}
    assert len(provider.calls) == 1
