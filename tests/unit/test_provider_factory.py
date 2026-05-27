import pytest

from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.providers.factory import build_provider, register_provider
from metis.providers.fake import FakeProvider
from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.errors import MetisError
from metis.runtime.response import NormalizedResponse


class StubProvider(BaseProvider):
    async def complete(self, messages, tools=None, **params):
        return NormalizedResponse(text="stub", tool_calls=[])


def test_build_provider_creates_openai_compat(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    provider = build_provider(provider_type="openai_compat", model="test-model", base_url="http://localhost:8000")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "test-model"


def test_build_provider_creates_fake():
    provider = build_provider(provider_type="fake", responses=[NormalizedResponse(content="hi", tool_calls=[])])
    assert isinstance(provider, FakeProvider)


def test_build_provider_unknown_type_raises():
    with pytest.raises(MetisError, match="Unknown provider type 'nonexistent'"):
        build_provider(provider_type="nonexistent")


def test_register_provider_custom_type():
    register_provider("stub", StubProvider)
    provider = build_provider(provider_type="stub")
    assert isinstance(provider, StubProvider)


def test_register_provider_rejects_non_subclass():
    with pytest.raises(TypeError, match="not a BaseProvider subclass"):
        register_provider("bad", dict)


def test_default_provider_is_openai_compat(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    provider = build_provider(model="test")
    assert isinstance(provider, OpenAICompatibleProvider)
