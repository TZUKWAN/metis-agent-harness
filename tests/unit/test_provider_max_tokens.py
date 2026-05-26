"""Tests for automatic max_tokens in provider requests."""

from __future__ import annotations

import os

import httpx
import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider


class _MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


def test_auto_max_tokens_from_detected_capabilities(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("METIS_BASE_URL", "http://test")
    monkeypatch.setenv("METIS_API_KEY", "key")
    provider = OpenAICompatibleProvider(model="glm-4.7-flash")

    posted = {}
    original_post = httpx.AsyncClient.post

    async def fake_post(self, url, **kwargs):
        posted["payload"] = kwargs.get("json")
        return _MockResponse({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {},
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    import asyncio
    asyncio.run(provider.complete([{"role": "user", "content": "hi"}]))
    assert posted["payload"]["max_tokens"] == 8192


def test_explicit_max_tokens_preserved(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("METIS_BASE_URL", "http://test")
    monkeypatch.setenv("METIS_API_KEY", "key")
    provider = OpenAICompatibleProvider(model="glm-4.7-flash")

    posted = {}

    async def fake_post(self, url, **kwargs):
        posted["payload"] = kwargs.get("json")
        return _MockResponse({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {},
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    import asyncio
    asyncio.run(provider.complete([{"role": "user", "content": "hi"}], max_tokens=512))
    assert posted["payload"]["max_tokens"] == 512


def test_env_var_overrides_auto(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("METIS_BASE_URL", "http://test")
    monkeypatch.setenv("METIS_API_KEY", "key")
    monkeypatch.setenv("METIS_PROVIDER_MAX_TOKENS", "2048")
    provider = OpenAICompatibleProvider(model="glm-4.7-flash")

    posted = {}

    async def fake_post(self, url, **kwargs):
        posted["payload"] = kwargs.get("json")
        return _MockResponse({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {},
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    import asyncio
    asyncio.run(provider.complete([{"role": "user", "content": "hi"}]))
    assert posted["payload"]["max_tokens"] == 2048


def test_zero_detected_skips_max_tokens(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("METIS_BASE_URL", "http://test")
    monkeypatch.setenv("METIS_API_KEY", "key")
    provider = OpenAICompatibleProvider(model="unknown-model")

    posted = {}

    async def fake_post(self, url, **kwargs):
        posted["payload"] = kwargs.get("json")
        return _MockResponse({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {},
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    import asyncio
    asyncio.run(provider.complete([{"role": "user", "content": "hi"}]))
    assert "max_tokens" not in posted["payload"]
