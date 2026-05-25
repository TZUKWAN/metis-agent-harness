"""Swarm audit utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metis.quality.runner import QualityGateRunner


@dataclass(frozen=True)
class AuditReport:
    passed: bool
    messages: list[str] = field(default_factory=list)


class Auditor:
    def __init__(self, quality_runner: QualityGateRunner | None = None) -> None:
        self.quality_runner = quality_runner or QualityGateRunner()

    def audit(self, *, final_text: str, artifacts: list[Any], evidence: list[Any], tool_results: list[Any]) -> AuditReport:
        result = self.quality_runner.run(
            ["artifact_exists", "artifact_non_empty", "no_fake_completion"],
            {"final_text": final_text, "artifacts": artifacts, "evidence": evidence, "tool_results": tool_results},
        )
        return AuditReport(result.passed, [item.message for item in result.results])
