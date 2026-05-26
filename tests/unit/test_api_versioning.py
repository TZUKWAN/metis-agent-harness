"""Tests for API versioning: /api/v1/ endpoints and legacy redirects."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from metis.app.manifest import AgentAppManifest
from metis.app.web import create_app


@pytest.fixture
def client():
    manifest = AgentAppManifest(name="test", version="1.0.0", model="test-model")
    app = create_app(manifest)
    return TestClient(app)


class TestV1Endpoints:
    def test_v1_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"
        assert data["model"] == "test-model"

    def test_v1_config(self, client):
        resp = client.get("/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"

    def test_v1_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200

    def test_v1_tools(self, client):
        resp = client.get("/api/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    def test_v1_sessions_list(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_v1_session_detail_not_found(self, client):
        resp = client.get("/api/v1/sessions/nonexistent")
        assert resp.status_code == 404

    def test_v1_session_delete(self, client):
        resp = client.delete("/api/v1/sessions/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == "nonexistent"
        assert data["existed"] is False

    def test_v1_session_usage(self, client):
        resp = client.get("/api/v1/sessions/test-session/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt_tokens" in data
        assert "completion_tokens" in data

    def test_v1_health_uptime(self, client):
        import time
        time.sleep(0.1)
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0


class TestLegacyRedirects:
    def test_legacy_health_redirects(self, client):
        resp = client.get("/api/health", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/health" in resp.headers["location"]

    def test_legacy_config_redirects(self, client):
        resp = client.get("/api/config", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/config" in resp.headers["location"]

    def test_legacy_status_redirects(self, client):
        resp = client.get("/api/status", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/status" in resp.headers["location"]

    def test_legacy_tools_redirects(self, client):
        resp = client.get("/api/tools", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/tools" in resp.headers["location"]

    def test_legacy_sessions_redirects(self, client):
        resp = client.get("/api/sessions", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/sessions" in resp.headers["location"]

    def test_legacy_session_detail_redirects(self, client):
        resp = client.get("/api/sessions/abc123", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/sessions/abc123" in resp.headers["location"]

    def test_legacy_session_delete_redirects(self, client):
        resp = client.delete("/api/sessions/abc123", follow_redirects=False)
        assert resp.status_code == 307

    def test_legacy_session_usage_redirects(self, client):
        resp = client.get("/api/sessions/abc123/usage", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/v1/sessions/abc123/usage" in resp.headers["location"]

    def test_legacy_chat_endpoint_exists(self, client):
        resp = client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_v1_chat_endpoint_exists(self, client):
        resp = client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422


class TestVersionPrefixConsistency:
    def test_all_v1_get_endpoints_exist(self, client):
        endpoints = [
            "/api/v1/health",
            "/api/v1/config",
            "/api/v1/status",
            "/api/v1/tools",
            "/api/v1/sessions",
        ]
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert resp.status_code == 200, f"GET {endpoint} failed: {resp.status_code}"

    def test_response_headers_include_request_id(self, client):
        resp = client.get("/api/v1/health")
        assert "X-Request-ID" in resp.headers
        assert "X-Response-Time" in resp.headers
