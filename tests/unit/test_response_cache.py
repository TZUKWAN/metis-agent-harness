"""Tests for ResponseCache."""

from __future__ import annotations

import time

import pytest

from metis.providers.response_cache import ResponseCache


class TestResponseCache:
    def test_cache_hit(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        tools = []
        cache.put(messages, tools, {"data": "result"})
        assert cache.get(messages, tools) == {"data": "result"}

    def test_cache_miss(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        assert cache.get([{"role": "user", "content": "hi"}], None) is None

    def test_cache_ttl_expires(self):
        cache = ResponseCache(max_size=10, ttl_seconds=0.01)
        messages = [{"role": "user", "content": "hello"}]
        cache.put(messages, None, "result")
        time.sleep(0.02)
        assert cache.get(messages, None) is None

    def test_cache_max_size_evicts_oldest(self):
        cache = ResponseCache(max_size=2, ttl_seconds=60)
        cache.put([{"role": "user", "content": "a"}], None, "A")
        cache.put([{"role": "user", "content": "b"}], None, "B")
        cache.put([{"role": "user", "content": "c"}], None, "C")
        assert cache.get([{"role": "user", "content": "a"}], None) is None
        assert cache.get([{"role": "user", "content": "b"}], None) == "B"
        assert cache.get([{"role": "user", "content": "c"}], None) == "C"

    def test_cache_tools_differ(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        cache.put(messages, None, "no_tools")
        cache.put(messages, [{"name": "tool1"}], "with_tools")
        assert cache.get(messages, None) == "no_tools"
        assert cache.get(messages, [{"name": "tool1"}]) == "with_tools"

    def test_cache_clear(self):
        cache = ResponseCache(max_size=10, ttl_seconds=60)
        cache.put([{"role": "user", "content": "hello"}], None, "result")
        cache.clear()
        assert cache.size == 0
        assert cache.get([{"role": "user", "content": "hello"}], None) is None

    def test_cache_order_updates_on_access(self):
        cache = ResponseCache(max_size=2, ttl_seconds=60)
        cache.put([{"role": "user", "content": "a"}], None, "A")
        cache.put([{"role": "user", "content": "b"}], None, "B")
        cache.get([{"role": "user", "content": "a"}], None)
        cache.put([{"role": "user", "content": "c"}], None, "C")
        assert cache.get([{"role": "user", "content": "a"}], None) == "A"
        assert cache.get([{"role": "user", "content": "b"}], None) is None
