"""Tests for runtime integration with ModelRouter."""

from __future__ import annotations

import pytest

from metis.app.manifest import AgentAppManifest
from metis.app.runtime import _build_provider_for_manifest
from metis.routing.router import ModelRouter


def test_build_single_provider_backward_compatible(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    manifest = AgentAppManifest(model="glm-4.7-flash", base_url="http://localhost:8000")
    provider = _build_provider_for_manifest(manifest)
    assert not isinstance(provider, ModelRouter)
    caps = provider.capabilities()
    assert caps.model == "glm-4.7-flash"


def test_build_model_router_from_manifest(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    manifest = AgentAppManifest(
        model="glm-4.7-flash",
        providers=[
            {"name": "primary", "model": "glm-4.7-flash", "priority": 10},
            {"name": "fallback", "model": "glm-4", "priority": 5},
        ],
    )
    provider = _build_provider_for_manifest(manifest)
    assert isinstance(provider, ModelRouter)
    stats = provider.get_stats()
    assert stats["provider_names"] == ["primary", "fallback"]


def test_build_model_router_with_fallback_providers(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    manifest = AgentAppManifest(
        model="glm-4.7-flash",
        providers=[
            {"name": "primary", "model": "glm-4.7-flash", "priority": 10},
        ],
        fallback_providers=[
            {"name": "fb1", "model": "glm-4", "priority": 0},
        ],
    )
    provider = _build_provider_for_manifest(manifest)
    assert isinstance(provider, ModelRouter)
    stats = provider.get_stats()
    assert "primary" in stats["provider_names"]
    assert "fb1" in stats["provider_names"]


def test_build_single_provider_when_only_one_configured(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    manifest = AgentAppManifest(
        providers=[
            {"name": "only", "model": "glm-4.7-flash"},
        ],
    )
    provider = _build_provider_for_manifest(manifest)
    assert not isinstance(provider, ModelRouter)


def test_build_model_router_with_capability_strategy(monkeypatch):
    monkeypatch.setenv("METIS_API_KEY", "test-key")
    monkeypatch.setenv("METIS_BASE_URL", "http://localhost:8000")
    manifest = AgentAppManifest(
        providers=[
            {"name": "p1", "model": "glm-4.7-flash"},
            {"name": "p2", "model": "glm-4"},
        ],
        routing_strategy="capability_match",
    )
    provider = _build_provider_for_manifest(manifest)
    assert isinstance(provider, ModelRouter)


def test_manifest_fields_preserves_provider_lists():
    data = {
        "providers": [{"name": "p1", "model": "m1"}],
        "fallback_providers": [{"name": "fb1", "model": "m2"}],
        "routing_strategy": "capability_match",
        "provider_health_check_interval": 30.0,
        "provider_failover_enabled": True,
    }
    manifest = AgentAppManifest(**data)
    assert len(manifest.providers) == 1
    assert manifest.providers[0]["name"] == "p1"
    assert len(manifest.fallback_providers) == 1
    assert manifest.routing_strategy == "capability_match"
    assert manifest.provider_health_check_interval == 30.0
    assert manifest.provider_failover_enabled is True
