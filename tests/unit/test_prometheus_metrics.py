"""Tests for Prometheus metrics export."""

from __future__ import annotations

from metis.app.metrics import MetricsStore


def test_prometheus_format_empty():
    store = MetricsStore()
    output = store.prometheus_format()
    assert "metis_requests_total" in output
    assert "metis_errors_total" in output


def test_prometheus_format_with_data():
    store = MetricsStore()
    store.record("/api/v1/health", "GET", 200, 12.5)
    store.record("/api/v1/chat", "POST", 200, 250.0)
    store.record("/api/v1/chat", "POST", 500, 100.0)
    output = store.prometheus_format()
    assert "metis_requests_total" in output
    assert "method=\"GET\"" in output
    assert "method=\"POST\"" in output
    assert "metis_errors_total" in output
    assert "metis_request_duration_ms_avg" in output
    assert "metis_request_duration_ms_p95" in output


def test_prometheus_escapes_quotes():
    store = MetricsStore()
    store.record("/api/v1/health", "GET", 200, 1.0)
    output = store.prometheus_format()
    assert 'method="GET"' in output
