"""In-memory metrics store for API observability."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestMetric:
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


class MetricsStore:
    """Keep a rolling window of request metrics."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: deque[RequestMetric] = deque(maxlen=max_entries)

    def record(self, endpoint: str, method: str, status_code: int, duration_ms: float) -> None:
        self._entries.append(RequestMetric(endpoint, method, status_code, duration_ms))

    def summary(self) -> dict[str, Any]:
        if not self._entries:
            return {"total_requests": 0, "endpoints": {}}

        total = len(self._entries)
        durations = [e.duration_ms for e in self._entries]
        errors = [e for e in self._entries if e.status_code >= 400]

        endpoint_stats: dict[str, dict[str, Any]] = {}
        for entry in self._entries:
            key = f"{entry.method} {entry.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = {"count": 0, "errors": 0, "durations": []}
            endpoint_stats[key]["count"] += 1
            endpoint_stats[key]["durations"].append(entry.duration_ms)
            if entry.status_code >= 400:
                endpoint_stats[key]["errors"] += 1

        for stats in endpoint_stats.values():
            durs = stats.pop("durations")
            stats["avg_duration_ms"] = round(sum(durs) / len(durs), 2) if durs else 0
            stats["p95_duration_ms"] = round(sorted(durs)[int(len(durs) * 0.95)] if durs else 0, 2)

        return {
            "total_requests": total,
            "error_count": len(errors),
            "error_rate": round(len(errors) / total, 4) if total else 0,
            "avg_duration_ms": round(sum(durations) / total, 2) if total else 0,
            "endpoints": endpoint_stats,
        }

    def prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []
        lines.append("# HELP metis_requests_total Total HTTP requests")
        lines.append("# TYPE metis_requests_total counter")
        lines.append("# HELP metis_request_duration_ms Request duration in milliseconds")
        lines.append("# TYPE metis_request_duration_ms summary")
        lines.append("# HELP metis_errors_total Total HTTP errors (4xx/5xx)")
        lines.append("# TYPE metis_errors_total counter")

        endpoint_counts: dict[str, int] = {}
        endpoint_errors: dict[str, int] = {}
        endpoint_durations: dict[str, list[float]] = {}

        for entry in self._entries:
            key = f'method=\"{entry.method}\",endpoint=\"{entry.endpoint}\",status=\"{entry.status_code}\"'
            endpoint_counts[key] = endpoint_counts.get(key, 0) + 1
            if entry.status_code >= 400:
                err_key = f'method=\"{entry.method}\",endpoint=\"{entry.endpoint}\"'
                endpoint_errors[err_key] = endpoint_errors.get(err_key, 0) + 1
            dur_key = f'method=\"{entry.method}\",endpoint=\"{entry.endpoint}\"'
            if dur_key not in endpoint_durations:
                endpoint_durations[dur_key] = []
            endpoint_durations[dur_key].append(entry.duration_ms)

        for key, count in endpoint_counts.items():
            lines.append(f'metis_requests_total{{{key}}} {count}')

        for key, errs in endpoint_errors.items():
            lines.append(f'metis_errors_total{{{key}}} {errs}')

        for key, durs in endpoint_durations.items():
            avg = sum(durs) / len(durs)
            p95 = sorted(durs)[int(len(durs) * 0.95)] if durs else 0
            lines.append(f'metis_request_duration_ms_avg{{{key}}} {round(avg, 2)}')
            lines.append(f'metis_request_duration_ms_p95{{{key}}} {round(p95, 2)}')

        return "\n".join(lines) + "\n"
