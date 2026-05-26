"""Tool usage analytics tracking per category and tool name."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolUsageStats:
    calls: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0


class ToolAnalytics:
    """Collect tool usage statistics."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolUsageStats] = defaultdict(ToolUsageStats)
        self._categories: dict[str, ToolUsageStats] = defaultdict(ToolUsageStats)

    def record(self, tool_name: str, category: str, duration_ms: float, status: str) -> None:
        t = self._tools[tool_name]
        t.calls += 1
        t.total_duration_ms += duration_ms
        if status != "ok":
            t.errors += 1

        c = self._categories[category]
        c.calls += 1
        c.total_duration_ms += duration_ms
        if status != "ok":
            c.errors += 1

    def summary(self) -> dict[str, Any]:
        return {
            "tools": {
                name: {
                    "calls": s.calls,
                    "errors": s.errors,
                    "avg_duration_ms": round(s.total_duration_ms / s.calls, 2) if s.calls else 0,
                }
                for name, s in self._tools.items()
            },
            "categories": {
                cat: {
                    "calls": s.calls,
                    "errors": s.errors,
                    "avg_duration_ms": round(s.total_duration_ms / s.calls, 2) if s.calls else 0,
                }
                for cat, s in self._categories.items()
            },
        }

    def clear(self) -> None:
        self._tools.clear()
        self._categories.clear()
