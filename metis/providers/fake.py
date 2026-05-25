"""Deterministic provider for tests."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable

from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.runtime.response import NormalizedResponse, ToolCall


class FakeProvider(BaseProvider):
    def __init__(self, responses: Iterable[NormalizedResponse | dict[str, Any]]) -> None:
        self._responses = deque(self._coerce(item) for item in responses)
        self.calls: list[dict[str, Any]] = []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type="fake",
            model="fake",
            native_tool_calling=True,
            json_schema_output=True,
            streaming=False,
            thinking=False,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> NormalizedResponse:
        self.calls.append({"messages": list(messages), "tools": tools or [], "params": dict(params)})
        if not self._responses:
            return NormalizedResponse(content="", finish_reason="empty")
        return self._responses.popleft()

    @staticmethod
    def _coerce(item: NormalizedResponse | dict[str, Any]) -> NormalizedResponse:
        if isinstance(item, NormalizedResponse):
            return item
        tool_calls = [
            call if isinstance(call, ToolCall) else ToolCall(**call)
            for call in item.get("tool_calls", [])
        ]
        return NormalizedResponse(
            content=item.get("content", ""),
            reasoning=item.get("reasoning"),
            tool_calls=tool_calls,
            finish_reason=item.get("finish_reason", ""),
            usage=item.get("usage", {}),
            raw=item,
        )
