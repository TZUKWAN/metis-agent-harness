"""Tests for provider capability auto-detection."""

from __future__ import annotations

import os

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider


class TestProviderCapabilities:
    def test_glm47_flash_detects_thinking(self):
        provider = OpenAICompatibleProvider(model="glm-4.7-flash", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is True
        assert caps.max_context_tokens == 128_000
        assert caps.max_output_tokens == 8_192

    def test_glm45_detects_thinking(self):
        provider = OpenAICompatibleProvider(model="glm-4.5-flash", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is True

    def test_glm49_detects_larger_context(self):
        provider = OpenAICompatibleProvider(model="glm-4.9-air", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is True
        assert caps.max_context_tokens == 256_000
        assert caps.max_output_tokens == 16_384

    def test_glm4_no_thinking(self):
        provider = OpenAICompatibleProvider(model="glm-4", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is False

    def test_gpt4o_no_thinking(self):
        provider = OpenAICompatibleProvider(model="gpt-4o", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is False
        assert caps.max_context_tokens == 128_000

    def test_claude_sonnet_context(self):
        provider = OpenAICompatibleProvider(model="claude-3-5-sonnet-20241022", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is False
        assert caps.max_context_tokens == 200_000

    def test_unknown_model_defaults(self):
        provider = OpenAICompatibleProvider(model="unknown-model-v1", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is False
        assert caps.max_context_tokens == 0
        assert caps.max_output_tokens == 0

    def test_env_var_overrides_detection(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("METIS_PROVIDER_THINKING_SUPPORTED", "false")
        monkeypatch.setenv("METIS_PROVIDER_MAX_CONTEXT_TOKENS", "64000")
        provider = OpenAICompatibleProvider(model="glm-4.7-flash", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        assert caps.thinking is False
        assert caps.max_context_tokens == 64_000

    def test_to_dict_serializes_retryable_codes(self):
        provider = OpenAICompatibleProvider(model="gpt-4o", base_url="http://test", api_key="test")
        caps = provider.capabilities()
        data = caps.to_dict()
        assert isinstance(data["retryable_status_codes"], list)
        assert 429 in data["retryable_status_codes"]
