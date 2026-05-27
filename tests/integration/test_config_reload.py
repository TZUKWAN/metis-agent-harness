"""Integration tests for config hot-reload via setup API and file watching."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metis.app.manifest import AgentAppManifest, save_app_manifest
from metis.app.web import create_app


def test_setup_updates_profile() -> None:
    """POST /setup updates profile and returns it in response."""
    manifest = AgentAppManifest(name="Test", model="gpt-4o", profile="small")
    app = create_app(manifest)
    client = TestClient(app)

    response = client.post("/api/v1/setup", json={
        "model": "gpt-4o",
        "profile": "large",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "large"
    assert data["model"] == "gpt-4o"


def test_setup_updates_hitl_enabled() -> None:
    """POST /setup updates hitl_enabled flag."""
    manifest = AgentAppManifest(name="Test", model="gpt-4o", hitl_enabled=False)
    app = create_app(manifest)
    client = TestClient(app)

    response = client.post("/api/v1/setup", json={
        "model": "gpt-4o",
        "hitl_enabled": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    # Verify manifest was updated
    assert app.state.manifest.hitl_enabled is True


def test_setup_preserve_existing_config() -> None:
    """POST /setup preserves existing config fields not in payload."""
    manifest = AgentAppManifest(
        name="Test",
        model="gpt-4o",
        profile="medium",
        hitl_enabled=True,
        workspace="/tmp/test",
    )
    app = create_app(manifest)
    client = TestClient(app)

    response = client.post("/api/v1/setup", json={
        "model": "claude-sonnet",
    })
    assert response.status_code == 200

    # Verify preserved fields
    assert app.state.manifest.profile == "medium"
    assert app.state.manifest.hitl_enabled is True
    assert app.state.manifest.workspace == "/tmp/test"
    # Verify changed field
    assert app.state.manifest.model == "claude-sonnet"


def test_config_endpoint_reflects_updates() -> None:
    """GET /config reflects changes made via POST /setup."""
    manifest = AgentAppManifest(name="Test", model="gpt-4o", profile="small")
    app = create_app(manifest)
    client = TestClient(app)

    client.post("/api/v1/setup", json={
        "model": "gpt-4o",
        "profile": "large",
    })

    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "large"


def test_setup_with_api_key_and_provider() -> None:
    """POST /setup stores API key in providers list."""
    manifest = AgentAppManifest(name="Test", model="gpt-4o")
    app = create_app(manifest)
    client = TestClient(app)

    response = client.post("/api/v1/setup", json={
        "model": "gpt-4o",
        "api_key": "sk-test123",
        "base_url": "https://custom.api.com/v1",
    })
    assert response.status_code == 200

    providers = app.state.manifest.providers
    assert len(providers) >= 1
    assert providers[0].get("model") == "gpt-4o"
    assert providers[0].get("api_key") == "sk-test123"
    assert providers[0].get("base_url") == "https://custom.api.com/v1"


def test_setup_rejects_empty_model() -> None:
    """POST /setup returns 422 if model is explicitly empty."""
    manifest = AgentAppManifest(name="Test", model="gpt-4o")
    app = create_app(manifest)
    client = TestClient(app)

    response = client.post("/api/v1/setup", json={
        "model": "",
        "base_url": "https://example.com",
    })
    assert response.status_code == 422
