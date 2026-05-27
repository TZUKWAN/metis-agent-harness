"""Tests for ProviderHealthMonitor."""

from __future__ import annotations

import asyncio

import pytest

from metis.routing.health import ProviderHealthMonitor


class FakeProvider:
    def __init__(self, healthy: bool = True, delay: float = 0.0, raise_error: bool = False) -> None:
        self.healthy = healthy
        self.delay = delay
        self.raise_error = raise_error
        self.health_check_calls = 0

    async def health_check(self) -> dict:
        self.health_check_calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raise_error:
            raise RuntimeError("health check error")
        if self.healthy:
            return {"status": "ok", "model": "fake"}
        return {"status": "error", "error": "unhealthy", "model": "fake"}


@pytest.mark.asyncio
async def test_register_and_check_once_healthy():
    monitor = ProviderHealthMonitor()
    provider = FakeProvider(healthy=True)
    monitor.register("p1", provider)
    result = await monitor.check_once("p1")
    assert result is True
    status = monitor.get_status("p1")
    assert status["healthy"] is True
    assert status["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_check_once_unhealthy():
    monitor = ProviderHealthMonitor(failure_threshold=1)
    provider = FakeProvider(healthy=False)
    monitor.register("p1", provider)
    result = await monitor.check_once("p1")
    assert result is False
    status = monitor.get_status("p1")
    assert status["healthy"] is False
    assert status["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_consecutive_failures_crosses_threshold():
    monitor = ProviderHealthMonitor(failure_threshold=2)
    provider = FakeProvider(healthy=False)
    monitor.register("p1", provider)
    await monitor.check_once("p1")
    status = monitor.get_status("p1")
    # Below threshold, still healthy (or at least not marked unhealthy yet)
    assert status["consecutive_failures"] == 1
    await monitor.check_once("p1")
    status = monitor.get_status("p1")
    assert status["consecutive_failures"] == 2
    assert status["healthy"] is False


@pytest.mark.asyncio
async def test_check_once_timeout():
    monitor = ProviderHealthMonitor(timeout_seconds=0.01)
    provider = FakeProvider(delay=1.0)
    monitor.register("p1", provider)
    result = await monitor.check_once("p1")
    assert result is False
    status = monitor.get_status("p1")
    assert status["last_error"] == "health check timed out"


@pytest.mark.asyncio
async def test_check_once_exception():
    monitor = ProviderHealthMonitor(failure_threshold=1)
    provider = FakeProvider(raise_error=True)
    monitor.register("p1", provider)
    result = await monitor.check_once("p1")
    assert result is False
    status = monitor.get_status("p1")
    assert "RuntimeError" in status["last_error"]


@pytest.mark.asyncio
async def test_check_all():
    monitor = ProviderHealthMonitor()
    p1 = FakeProvider(healthy=True)
    p2 = FakeProvider(healthy=False)
    monitor.register("p1", p1)
    monitor.register("p2", p2)
    results = await monitor.check_all()
    assert results == {"p1": True, "p2": False}


@pytest.mark.asyncio
async def test_unregister():
    monitor = ProviderHealthMonitor()
    provider = FakeProvider()
    monitor.register("p1", provider)
    monitor.unregister("p1")
    status = monitor.get_status("p1")
    assert status["healthy"] is True  # Default when unknown


@pytest.mark.asyncio
async def test_all_status():
    monitor = ProviderHealthMonitor()
    p1 = FakeProvider(healthy=True)
    p2 = FakeProvider(healthy=False)
    monitor.register("p1", p1)
    monitor.register("p2", p2)
    await monitor.check_all()
    all_status = monitor.all_status()
    assert len(all_status) == 2
    assert all_status["p1"]["healthy"] is True
    # p2 is unhealthy but default failure_threshold=2 means it takes 2 failures
    assert all_status["p2"]["consecutive_failures"] == 1
