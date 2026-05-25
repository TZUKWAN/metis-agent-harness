"""Rules for deciding whether a task should use swarm execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SwarmDecision:
    enabled: bool
    reasons: list[str]
    recommended_roles: list[str]


class SwarmAnalyzer:
    COMPLEX_MARKERS = ("多模块", "多智能体", "审核团队", "并行", "复杂", "全量测试", "架构")

    def analyze(self, task_text: str, *, failure_count: int = 0) -> SwarmDecision:
        reasons = [marker for marker in self.COMPLEX_MARKERS if marker.lower() in task_text.lower()]
        if failure_count >= 2:
            reasons.append("multiple failures")
        enabled = bool(reasons)
        roles = ["planner", "explorer", "implementer", "verifier", "auditor", "synthesizer"] if enabled else []
        return SwarmDecision(enabled, reasons, roles)
