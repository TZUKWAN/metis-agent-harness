"""Shared context for inter-agent communication in swarm orchestration."""

from __future__ import annotations

import asyncio
from typing import Any


class SharedContext:
    """Thread-safe key-value store for worker agents to share results."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._data.get(key, default)

    async def get_all(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._data)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()
