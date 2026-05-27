"""Tests for routing strategies."""

from __future__ import annotations

import pytest

from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.routing.strategy import (
    CapabilityMatchStrategy,
    PrimaryFallbackStrategy,
    ProviderEntry,
)


class FakeProvider(BaseProvider):
    def __init__(self, caps: ProviderCapabilities) -> None:
        self._caps = caps

    def capabilities(self) -> ProviderCapabilities:
        return self._caps

    async def complete(self, messages, tools=None, **params):
        return None  # type: ignore[return-value]


def make_entry(name: str, priority: int = 0, **caps) -> ProviderEntry:
    return ProviderEntry(
        name=name,
        provider=FakeProvider(ProviderCapabilities(provider_type="fake", model=name, **caps)),
        priority=priority,
    )


def test_primary_fallback_selects_highest_priority():
    strategy = PrimaryFallbackStrategy()
    providers = [
        make_entry("p1", priority=10),
        make_entry("p2", priority=5),
        make_entry("p3", priority=20),
    ]
    health = {p.name: {"healthy": True} for p in providers}
    selected = strategy.select(providers, health)
    assert selected is not None
    assert selected.name == "p3"


def test_primary_fallback_skips_unhealthy():
    strategy = PrimaryFallbackStrategy()
    providers = [
        make_entry("p1", priority=10),
        make_entry("p2", priority=5),
    ]
    health = {"p1": {"healthy": False}, "p2": {"healthy": True}}
    selected = strategy.select(providers, health)
    assert selected is not None
    assert selected.name == "p2"


def test_primary_fallback_returns_best_when_all_unhealthy():
    strategy = PrimaryFallbackStrategy()
    providers = [
        make_entry("p1", priority=10),
        make_entry("p2", priority=5),
    ]
    health = {"p1": {"healthy": False}, "p2": {"healthy": False}}
    selected = strategy.select(providers, health)
    assert selected is not None
    assert selected.name == "p1"


def test_primary_fallback_empty_providers():
    strategy = PrimaryFallbackStrategy()
    selected = strategy.select([], {})
    assert selected is None


def test_capability_match_prefers_native_tool_calling():
    strategy = CapabilityMatchStrategy()
    providers = [
        make_entry("p1", native_tool_calling=False),
        make_entry("p2", native_tool_calling=True),
    ]
    health = {p.name: {"healthy": True} for p in providers}
    selected = strategy.select(providers, health, required_capabilities={"native_tool_calling": True})
    assert selected is not None
    assert selected.name == "p2"


def test_capability_match_prefers_thinking():
    strategy = CapabilityMatchStrategy()
    providers = [
        make_entry("p1", thinking=False),
        make_entry("p2", thinking=True),
    ]
    health = {p.name: {"healthy": True} for p in providers}
    selected = strategy.select(providers, health, required_capabilities={"thinking": True})
    assert selected is not None
    assert selected.name == "p2"


def test_capability_match_falls_back_when_none_match():
    strategy = CapabilityMatchStrategy()
    providers = [
        make_entry("p1", priority=10),
        make_entry("p2", priority=5),
    ]
    health = {p.name: {"healthy": True} for p in providers}
    selected = strategy.select(providers, health, required_capabilities={"thinking": True})
    assert selected is not None
    assert selected.name == "p1"


def test_capability_match_skips_unhealthy():
    strategy = CapabilityMatchStrategy()
    providers = [
        make_entry("p1", native_tool_calling=True),
        make_entry("p2", native_tool_calling=True),
    ]
    health = {"p1": {"healthy": False}, "p2": {"healthy": True}}
    selected = strategy.select(providers, health, required_capabilities={"native_tool_calling": True})
    assert selected is not None
    assert selected.name == "p2"


def test_provider_entry_default_tags():
    entry = ProviderEntry(name="p1", provider=FakeProvider(ProviderCapabilities(provider_type="fake", model="m1")))
    assert entry.tags == []
