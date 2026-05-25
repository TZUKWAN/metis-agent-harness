"""Synthesize audited swarm results."""

from __future__ import annotations

from typing import Any


class ResultSynthesizer:
    def synthesize(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = [self._unwrap(item) for item in results]
        accepted = [item for item in normalized if item.get("audit_passed", item.get("status") != "failed")]
        return {
            "status": "done" if accepted else "blocked",
            "summary": "\n".join(str(item.get("summary", item.get("result", ""))) for item in accepted),
            "evidence_refs": [ref for item in accepted for ref in item.get("evidence_refs", [])],
            "artifact_refs": [ref for item in accepted for ref in item.get("artifact_refs", [])],
        }

    @staticmethod
    def _unwrap(item: dict[str, Any]) -> dict[str, Any]:
        nested = item.get("result")
        if isinstance(nested, dict):
            return dict(nested) | {"agent_id": item.get("agent_id"), "role_id": item.get("role_id")}
        return item
