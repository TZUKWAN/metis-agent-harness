"""Health monitoring and failover for model providers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from metis.logging import get_logger

logger = get_logger("routing.health")


@dataclass
class ProviderHealthRecord:
    """Health state for a single provider."""

    name: str
    healthy: bool = True
    last_check: float = 0.0
    consecutive_failures: int = 0
    last_error: str = ""
    check_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "check_count": self.check_count,
            "metadata": self.metadata,
        }


class ProviderHealthMonitor:
    """Monitor provider health with configurable thresholds."""

    def __init__(
        self,
        *,
        check_interval_seconds: float = 60.0,
        failure_threshold: int = 2,
        recovery_threshold: int = 1,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.check_interval_seconds = check_interval_seconds
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.timeout_seconds = timeout_seconds
        self._records: dict[str, ProviderHealthRecord] = {}
        self._providers: dict[str, Any] = {}
        self._task: asyncio.Task[Any] | None = None
        self._stop_event = asyncio.Event()

    def register(self, name: str, provider: Any) -> None:
        self._providers[name] = provider
        if name not in self._records:
            self._records[name] = ProviderHealthRecord(name=name)

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)
        self._records.pop(name, None)

    def get_status(self, name: str) -> dict[str, Any]:
        record = self._records.get(name)
        if record is None:
            return {"healthy": True, "name": name}
        return record.to_dict()

    def all_status(self) -> dict[str, dict[str, Any]]:
        return {name: record.to_dict() for name, record in self._records.items()}

    async def check_once(self, name: str) -> bool:
        provider = self._providers.get(name)
        if provider is None:
            return True
        record = self._records.setdefault(name, ProviderHealthRecord(name=name))
        record.check_count += 1
        try:
            result = await asyncio.wait_for(
                provider.health_check(),
                timeout=self.timeout_seconds,
            )
            healthy = result.get("status") == "ok"
            record.last_check = time.monotonic()
            record.metadata = dict(result)
            if healthy:
                record.consecutive_failures = 0
                record.last_error = ""
                if not record.healthy:
                    # Check if recovered enough
                    # We track recovery implicitly via consecutive healthy checks
                    pass
                record.healthy = True
            else:
                record.consecutive_failures += 1
                record.last_error = result.get("error", "unknown")
                if record.consecutive_failures >= self.failure_threshold:
                    record.healthy = False
            return healthy
        except asyncio.TimeoutError:
            record.last_check = time.monotonic()
            record.consecutive_failures += 1
            record.last_error = "health check timed out"
            if record.consecutive_failures >= self.failure_threshold:
                record.healthy = False
            return False
        except Exception as exc:
            record.last_check = time.monotonic()
            record.consecutive_failures += 1
            record.last_error = f"{type(exc).__name__}: {exc}"
            if record.consecutive_failures >= self.failure_threshold:
                record.healthy = False
            return False

    async def check_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name in list(self._providers):
            results[name] = await self.check_once(name)
        return results

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.check_all()
            except Exception as exc:
                logger.warning("Health check loop error: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.check_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
