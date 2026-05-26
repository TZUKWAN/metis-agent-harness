"""Provider abstraction for model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from metis.runtime.response import NormalizedResponse


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_type: str
    model: str
    native_tool_calling: bool = False
    json_schema_output: bool = False
    streaming: bool = False
    thinking: bool = False
    max_context_tokens: int = 0
    max_output_tokens: int = 0
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["retryable_status_codes"] = list(self.retryable_status_codes)
        return data


class BaseProvider(ABC):
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_type=type(self).__name__, model="")

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> NormalizedResponse:
        """Return a normalized completion response."""

    async def health_check(self) -> dict[str, Any]:
        """Lightweight check that the provider endpoint is reachable."""
        try:
            response = await self.complete(
                [{"role": "user", "content": "ping"}],
            )
            return {"status": "ok", "model": self.capabilities().model}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
