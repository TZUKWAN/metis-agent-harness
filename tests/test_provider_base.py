"""Tests for metis/providers/base.py."""

import pytest

from metis.providers.base import BaseProvider, ProviderCapabilities


class TestProviderCapabilities:
    def test_defaults(self):
        cap = ProviderCapabilities(provider_type="test", model="m1")
        assert cap.provider_type == "test"
        assert cap.model == "m1"
        assert not cap.native_tool_calling
        assert not cap.streaming
        assert cap.max_context_tokens == 0

    def test_to_dict(self):
        cap = ProviderCapabilities(provider_type="openai", model="gpt-4")
        d = cap.to_dict()
        assert d["provider_type"] == "openai"
        assert isinstance(d["retryable_status_codes"], list)

    def test_frozen(self):
        cap = ProviderCapabilities(provider_type="t", model="m")
        with pytest.raises(AttributeError):
            cap.model = "other"

    def test_custom_retry_codes(self):
        cap = ProviderCapabilities(provider_type="t", model="m", retryable_status_codes=(429,))
        assert cap.retryable_status_codes == (429,)


class TestBaseProvider:
    def test_default_capabilities(self):
        class ConcreteProvider(BaseProvider):
            async def complete(self, messages, tools=None, **params):
                pass

        p = ConcreteProvider()
        cap = p.capabilities()
        assert cap.provider_type == "ConcreteProvider"
        assert cap.model == ""

    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            BaseProvider()
