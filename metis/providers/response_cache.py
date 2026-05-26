"""LRU response cache for model completions."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any


class ResponseCache:
    """Cache model responses by request content hash. Thread-safe via GIL."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 300.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    @staticmethod
    def _make_key(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
        payload = json.dumps(
            {"messages": messages, "tools": tools or []},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> Any | None:
        key = self._make_key(messages, tools)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl_seconds:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return value

    def put(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, response: Any) -> None:
        key = self._make_key(messages, tools)
        self._cache[key] = (time.time(), response)
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
