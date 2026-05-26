"""Tests for metrics collection."""

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


class TestMetricsEndpoint:
    def test_metrics_endpoint_exists(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "endpoints" in data

    def test_metrics_tracks_requests(self, client):
        client.get("/api/v1/health")
        client.get("/api/v1/config")
        resp = client.get("/api/v1/metrics")
        data = resp.json()
        assert data["total_requests"] >= 2
        assert "GET /api/v1/health" in data["endpoints"]
        assert "GET /api/v1/config" in data["endpoints"]

    def test_metrics_calculates_avg_duration(self, client):
        client.get("/api/v1/health")
        resp = client.get("/api/v1/metrics")
        data = resp.json()
        ep = data["endpoints"]["GET /api/v1/health"]
        assert "avg_duration_ms" in ep
        assert ep["avg_duration_ms"] >= 0

    def test_metrics_empty_initially(self, client):
        resp = client.get("/api/v1/metrics")
        data = resp.json()
        assert data["total_requests"] == 0
        assert data["endpoints"] == {}

    def test_metrics_error_tracking(self, client):
        client.get("/api/v1/sessions/nonexistent")
        resp = client.get("/api/v1/metrics")
        data = resp.json()
        assert data["error_count"] == 1
        assert data["error_rate"] == 1.0
