"""Trajectory recording and JSONL export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrajectoryRecorder:
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"event_type": event_type, "payload": payload}
        self.events.append(event)
        return event

    def hook(self, event_type: str):
        def _handler(context: dict[str, Any]) -> dict[str, Any]:
            self.record(event_type, dict(context))
            return context

        return _handler

    def export_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in self.events), encoding="utf-8")
