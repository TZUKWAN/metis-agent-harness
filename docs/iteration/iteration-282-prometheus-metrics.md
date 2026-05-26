# Iteration 282: Prometheus Metrics Export Endpoint

## Problem
MetricsStore only provided a JSON summary endpoint. Production monitoring stacks (Prometheus/Grafana) require metrics in Prometheus text exposition format.

## Solution

1. **Prometheus text format**: Added `MetricsStore.prometheus_format()` that exports:
   - `metis_requests_total` - Counter, labeled by method/endpoint/status
   - `metis_errors_total` - Counter, labeled by method/endpoint
   - `metis_request_duration_ms_avg` - Average duration
   - `metis_request_duration_ms_p95` - P95 duration

2. **New endpoint**: `/api/v1/metrics/prometheus` returns `text/plain` Prometheus format

## Changes
- `metis/app/metrics.py`: Added `prometheus_format()` method
- `metis/app/web.py`: Added `/metrics/prometheus` endpoint

## Tests
- `tests/unit/test_prometheus_metrics.py`:
  - `test_prometheus_format_empty`
  - `test_prometheus_format_with_data`
  - `test_prometheus_escapes_quotes`

## Result
751 passed, 0 failed
