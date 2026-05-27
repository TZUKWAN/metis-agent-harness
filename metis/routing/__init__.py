"""Intelligent model routing with failover."""

from __future__ import annotations

from metis.routing.health import ProviderHealthMonitor, ProviderHealthRecord
from metis.routing.router import ModelRouter
from metis.routing.strategy import (
    CapabilityMatchStrategy,
    PrimaryFallbackStrategy,
    ProviderEntry,
    RoutingStrategy,
)

__all__ = [
    "CapabilityMatchStrategy",
    "ModelRouter",
    "PrimaryFallbackStrategy",
    "ProviderEntry",
    "ProviderHealthMonitor",
    "ProviderHealthRecord",
    "RoutingStrategy",
]
