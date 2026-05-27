"""Routing strategies for selecting providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from metis.providers.base import BaseProvider, ProviderCapabilities


@dataclass(frozen=True)
class ProviderEntry:
    """A provider with routing metadata."""

    name: str
    provider: BaseProvider
    priority: int = 0
    tags: list[str] = None  # type: ignore[assignment]
    cost_per_1k_tokens: float | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            object.__setattr__(self, "tags", [])


class RoutingStrategy(ABC):
    """Abstract base for provider selection strategies."""

    @abstractmethod
    def select(
        self,
        providers: list[ProviderEntry],
        health_status: dict[str, dict[str, Any]],
        *,
        required_capabilities: dict[str, Any] | None = None,
    ) -> ProviderEntry | None:
        """Select the best provider given health status and requirements."""


class PrimaryFallbackStrategy(RoutingStrategy):
    """Always prefer the highest-priority healthy provider; fall back in order."""

    def select(
        self,
        providers: list[ProviderEntry],
        health_status: dict[str, dict[str, Any]],
        *,
        required_capabilities: dict[str, Any] | None = None,
    ) -> ProviderEntry | None:
        sorted_providers = sorted(providers, key=lambda p: p.priority, reverse=True)
        for entry in sorted_providers:
            status = health_status.get(entry.name, {})
            if status.get("healthy", True):
                return entry
        # If no healthy provider, return the highest priority anyway (allow degraded mode)
        return sorted_providers[0] if sorted_providers else None


class CapabilityMatchStrategy(RoutingStrategy):
    """Select the provider whose capabilities best match the required ones."""

    def select(
        self,
        providers: list[ProviderEntry],
        health_status: dict[str, dict[str, Any]],
        *,
        required_capabilities: dict[str, Any] | None = None,
    ) -> ProviderEntry | None:
        if not providers:
            return None

        candidates: list[tuple[int, ProviderEntry]] = []
        for entry in providers:
            status = health_status.get(entry.name, {})
            if not status.get("healthy", True):
                continue
            score = self._score(entry.provider.capabilities(), required_capabilities or {})
            candidates.append((score, entry))

        if not candidates:
            # Fall back to primary-fallback if no capability match
            return PrimaryFallbackStrategy().select(providers, health_status)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _score(caps: ProviderCapabilities, required: dict[str, Any]) -> int:
        score = 0
        if required.get("native_tool_calling") and caps.native_tool_calling:
            score += 10
        if required.get("thinking") and caps.thinking:
            score += 10
        if required.get("json_schema_output") and caps.json_schema_output:
            score += 5
        if required.get("streaming") and caps.streaming:
            score += 3
        # Prefer larger context windows when requested
        req_ctx = required.get("max_context_tokens")
        if isinstance(req_ctx, int) and req_ctx > 0 and caps.max_context_tokens >= req_ctx:
            score += 5
        return score
