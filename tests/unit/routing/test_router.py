"""Tests for ModelRouter."""

from __future__ import annotations

import asyncio

import pytest

from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.runtime.errors import ProviderError
from metis.runtime.response import NormalizedResponse
from metis.routing.health import ProviderHealthMonitor
from metis.routing.router import ModelRouter
from metis.routing.strategy import CapabilityMatchStrategy, PrimaryFallbackStrategy, ProviderEntry


class FakeProvider(BaseProvider):
    def __init__(
        self,
        name: str = "fake",
        responses: list[NormalizedResponse] | None = None,
        raise_error: bool = False,
        raise_timeout: bool = False,
        delay: float = 0.0,
        caps: dict | None = None,
    ) -> None:
        self.name = name
        self._responses = list(responses or [NormalizedResponse(content=f"from_{name}")])
        self._index = 0
        self.raise_error = raise_error
        self.raise_timeout = raise_timeout
        self.delay = delay
        self._caps = caps or {}
        self.calls: list[dict] = []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type="fake",
            model=self.name,
            **self._caps,
        )

    async def complete(self, messages, tools=None, **params):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.calls.append({"messages": messages, "tools": tools, "params": params})
        if self.raise_timeout:
            raise asyncio.TimeoutError(f"{self.name} timed out")
        if self.raise_error:
            raise RuntimeError(f"{self.name} failed")
        resp = self._responses[self._index % len(self._responses)]
        self._index += 1
        return resp


def make_entry(name: str, priority: int = 0, **kwargs) -> ProviderEntry:
    return ProviderEntry(name=name, provider=FakeProvider(name=name, **kwargs), priority=priority)


@pytest.mark.asyncio
async def test_router_requires_at_least_one_provider():
    with pytest.raises(ValueError, match="at least one provider"):
        ModelRouter([])


@pytest.mark.asyncio
async def test_router_selects_primary_provider():
    router = ModelRouter([
        make_entry("p1", priority=10),
        make_entry("p2", priority=5),
    ])
    response = await router.complete([{"role": "user", "content": "hi"}])
    assert response.content == "from_p1"


@pytest.mark.asyncio
async def test_router_failover_to_secondary():
    p1 = FakeProvider(name="p1", raise_error=True)
    p2 = FakeProvider(name="p2")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ], failover_on_error=True)
    response = await router.complete([{"role": "user", "content": "hi"}])
    assert response.content == "from_p2"
    assert len(p1.calls) == 1
    assert len(p2.calls) == 1


@pytest.mark.asyncio
async def test_router_no_failover_when_disabled():
    p1 = FakeProvider(name="p1", raise_error=True)
    p2 = FakeProvider(name="p2")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ], failover_on_error=False)
    with pytest.raises(RuntimeError, match="p1 failed"):
        await router.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_router_all_providers_fail():
    p1 = FakeProvider(name="p1", raise_error=True)
    p2 = FakeProvider(name="p2", raise_error=True)
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ])
    with pytest.raises(ProviderError, match="All providers failed"):
        await router.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_router_failover_on_timeout():
    p1 = FakeProvider(name="p1", raise_timeout=True)
    p2 = FakeProvider(name="p2")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ], failover_on_error=True)
    response = await router.complete([{"role": "user", "content": "hi"}])
    assert response.content == "from_p2"


@pytest.mark.asyncio
async def test_router_capabilities_returns_active():
    p1 = FakeProvider(name="p1", caps={"thinking": True})
    p2 = FakeProvider(name="p2", caps={"thinking": False})
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ])
    caps = router.capabilities()
    assert caps.model == "p1"
    assert caps.thinking is True


@pytest.mark.asyncio
async def test_router_health_check():
    p1 = FakeProvider(name="p1")
    p2 = FakeProvider(name="p2")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ])
    result = await router.health_check()
    assert result["status"] == "ok"
    assert "p1" in result["providers"]
    assert "p2" in result["providers"]


@pytest.mark.asyncio
async def test_router_with_health_monitor():
    p1 = FakeProvider(name="p1", raise_error=True)
    p2 = FakeProvider(name="p2")
    health = ProviderHealthMonitor(failure_threshold=1)
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ], health_monitor=health, failover_on_error=True)
    response = await router.complete([{"role": "user", "content": "hi"}])
    assert response.content == "from_p2"


@pytest.mark.asyncio
async def test_router_stats():
    p1 = FakeProvider(name="p1")
    p2 = FakeProvider(name="p2")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ])
    await router.complete([{"role": "user", "content": "hi"}])
    stats = router.get_stats()
    assert stats["call_counts"]["p1"] == 1
    assert stats["active_provider"] == "p1"
    assert "avg_latencies" in stats


@pytest.mark.asyncio
async def test_router_with_capability_strategy():
    p1 = FakeProvider(name="p1", caps={"native_tool_calling": False})
    p2 = FakeProvider(name="p2", caps={"native_tool_calling": True})
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
    ], strategy=CapabilityMatchStrategy(), required_capabilities={"native_tool_calling": True})
    response = await router.complete([{"role": "user", "content": "hi"}])
    assert response.content == "from_p2"


@pytest.mark.asyncio
async def test_router_active_provider_property():
    p1 = FakeProvider(name="p1")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
    ])
    assert router.active_provider_name == "p1"
    assert router.active_provider is not None


@pytest.mark.asyncio
async def test_router_build_try_order():
    p1 = FakeProvider(name="p1")
    p2 = FakeProvider(name="p2")
    p3 = FakeProvider(name="p3")
    router = ModelRouter([
        ProviderEntry(name="p1", provider=p1, priority=10),
        ProviderEntry(name="p2", provider=p2, priority=5),
        ProviderEntry(name="p3", provider=p3, priority=1),
    ])
    primary = ProviderEntry(name="p2", provider=p2, priority=5)
    ordered = router._build_try_order(primary)
    assert ordered[0].name == "p2"
    assert ordered[1].name == "p1"
    assert ordered[2].name == "p3"
