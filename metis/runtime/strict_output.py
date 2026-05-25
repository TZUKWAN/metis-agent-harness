"""Strict final output contract for small-model runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


STRICT_OUTPUT_INSTRUCTIONS = (
    "Final response contract: return a single JSON object with exactly these keys: "
    "status, summary, evidence_refs, artifact_refs, next_action. "
    "status must be one of done, blocked, needs_more_work. evidence_refs and artifact_refs must be arrays."
)


@dataclass(frozen=True)
class StrictOutput:
    status: str
    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    next_action: str = ""


class StrictOutputError(ValueError):
    pass


class StrictOutputParser:
    required_keys = {"status", "summary", "evidence_refs", "artifact_refs", "next_action"}
    allowed_statuses = {"done", "blocked", "needs_more_work"}

    def parse(self, text: str) -> StrictOutput:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StrictOutputError(f"Final output is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise StrictOutputError("Final output must be a JSON object")
        missing = self.required_keys - set(data)
        if missing:
            raise StrictOutputError(f"Final output missing keys: {', '.join(sorted(missing))}")
        extra = set(data) - self.required_keys
        if extra:
            raise StrictOutputError(f"Final output has extra keys: {', '.join(sorted(extra))}")
        if data["status"] not in self.allowed_statuses:
            raise StrictOutputError(f"Unsupported final status: {data['status']}")
        if not isinstance(data["summary"], str) or not isinstance(data["next_action"], str):
            raise StrictOutputError("summary and next_action must be strings")
        if not isinstance(data["evidence_refs"], list) or not isinstance(data["artifact_refs"], list):
            raise StrictOutputError("evidence_refs and artifact_refs must be arrays")
        if not all(isinstance(item, str) for item in data["evidence_refs"] + data["artifact_refs"]):
            raise StrictOutputError("evidence_refs and artifact_refs must contain strings only")
        return StrictOutput(
            status=str(data["status"]),
            summary=data["summary"],
            evidence_refs=list(data["evidence_refs"]),
            artifact_refs=list(data["artifact_refs"]),
            next_action=data["next_action"],
        )

    @staticmethod
    def repair_prompt(error: Exception, bad_output: str) -> dict[str, Any]:
        return {
            "role": "user",
            "content": (
                "Your previous final response violated the strict output contract.\n"
                f"Error: {error}\n"
                f"{STRICT_OUTPUT_INSTRUCTIONS}\n"
                "Return only corrected JSON. Previous output:\n"
                f"{bad_output}"
            ),
        }
