"""ModelRouter: multi-provider routing with failover."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from metis.logging import get_logger
from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.runtime.errors import ProviderError
from metis.runtime.response import NormalizedResponse

from .health import ProviderHealthMonitor
from .strategy import CapabilityMatchStrategy, PrimaryFallbackStrategy, ProviderEntry, RoutingStrategy

logger = get_logger("routing.router")


class ModelRouter(BaseProvider):
    """Routes completion requests across multiple providers with failover."""

    def __init__(
        self,
        providers: list[ProviderEntry],
        *,
        strategy: RoutingStrategy | None = None,
        health_monitor: ProviderHealthMonitor | None = None,
        failover_on_error: bool = True,
        required_capabilities: dict[str, Any] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("ModelRouter requires at least one provider")
        self._providers = {p.name: p for p in providers}
        self._entries = list(providers)
        self._strategy = strategy or PrimaryFallbackStrategy()
        self._health = health_monitor
        self._failover_on_error = failover_on_error
        self._required_capabilities = required_capabilities or {}
        self._active_provider_name: str | None = None
        self._call_counts: dict[str, int] = {p.name: 0 for p in providers}
        self._error_counts: dict[str, int] = {p.name: 0 for p in providers}
        self._latencies: dict[str, list[float]] = {p.name: [] for p in providers}

        # Register providers with health monitor if provided
        if self._health is not None:
            for entry in providers:
                self._health.register(entry.name, entry.provider)

    @property
    def active_provider(self) -> BaseProvider | None:
        name = self._select_provider_name()
        if name is None:
            return None
        entry = self._providers.get(name)
        return entry.provider if entry else None

    @property
    def active_provider_name(self) -> str | None:
        return self._select_provider_name()

    def capabilities(self) -> ProviderCapabilities:
        active = self.active_provider
        if active is not None:
            return active.capabilities()
        # Return capabilities of highest-priority provider as default
        sorted_entries = sorted(self._entries, key=lambda p: p.priority, reverse=True)
        return sorted_entries[0].provider.capabilities()

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> NormalizedResponse:
        health = self._health.all_status() if self._health else {}
        selected = self._strategy.select(
            self._entries,
            health,
            required_capabilities=self._required_capabilities,
        )
        if selected is None:
            raise ProviderError("No provider available for routing")

        providers_to_try = self._build_try_order(selected)
        last_error: Exception | None = None

        for entry in providers_to_try:
            start = time.monotonic()
            self._call_counts[entry.name] = self._call_counts.get(entry.name, 0) + 1
            try:
                logger.debug("Routing to provider '%s' (priority=%d)", entry.name, entry.priority)
                response = await entry.provider.complete(messages, tools=tools, **params)
                latency = time.monotonic() - start
                self._latencies.setdefault(entry.name, []).append(latency)
                self._active_provider_name = entry.name
                # Trim latency history
                if len(self._latencies[entry.name]) > 100:
                    self._latencies[entry.name] = self._latencies[entry.name][-100:]
                return response
            except asyncio.TimeoutError as exc:
                last_error = exc
                self._error_counts[entry.name] = self._error_counts.get(entry.name, 0) + 1
                logger.warning("Provider '%s' timed out", entry.name)
                if not self._failover_on_error:
                    raise
                if self._health is not None:
                    await self._health.check_once(entry.name)
            except Exception as exc:
                last_error = exc
                self._error_counts[entry.name] = self._error_counts.get(entry.name, 0) + 1
                logger.warning("Provider '%s' failed: %s", entry.name, exc)
                if not self._failover_on_error:
                    raise
                if self._health is not None:
                    await self._health.check_once(entry.name)

        raise ProviderError(
            f"All providers failed. Last error: {last_error}"
        ) from last_error

    async def health_check(self) -> dict[str, Any]:
        if self._health is not None:
            await self._health.check_all()
            return {
                "status": "ok",
                "providers": self._health.all_status(),
                "active_provider": self._active_provider_name,
                "call_counts": dict(self._call_counts),
                "error_counts": dict(self._error_counts),
            }
        results: dict[str, Any] = {}
        for entry in self._entries:
            try:
                results[entry.name] = await asyncio.wait_for(
                    entry.provider.health_check(),
                    timeout=10.0,
                )
            except Exception as exc:
                results[entry.name] = {"status": "error", "error": str(exc)}
        any_healthy = any(
            r.get("status") == "ok" for r in results.values()
        )
        return {
            "status": "ok" if any_healthy else "error",
            "providers": results,
            "active_provider": self._active_provider_name,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return routing statistics."""
        return {
            "call_counts": dict(self._call_counts),
            "error_counts": dict(self._error_counts),
            "avg_latencies": {
                name: round(sum(vals) / len(vals), 3) if vals else 0.0
                for name, vals in self._latencies.items()
            },
            "active_provider": self._active_provider_name,
            "provider_names": list(self._providers),
        }

    def _select_provider_name(self) -> str | None:
        health = self._health.all_status() if self._health else {}
        selected = self._strategy.select(
            self._entries,
            health,
            required_capabilities=self._required_capabilities,
        )
        return selected.name if selected else None

    def _build_try_order(self, primary: ProviderEntry) -> list[ProviderEntry]:
        """Build ordered list of providers to try, starting with primary."""
        ordered = [primary]
        for entry in sorted(self._entries, key=lambda p: p.priority, reverse=True):
            if entry.name != primary.name:
                ordered.append(entry)
        return ordered

    async def close(self) -> None:
        if self._health is not None:
            await self._health.stop()
        for entry in self._entries:
            if hasattr(entry.provider, "close"):
                await entry.provider.close()  # type: ignore[misc]
