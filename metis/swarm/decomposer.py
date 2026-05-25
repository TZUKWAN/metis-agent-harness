"""Deterministic swarm task decomposition."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    role_id: str
    prompt: str


@dataclass(frozen=True)
class SwarmStage:
    stage_id: str
    parallel: bool
    agents: list[AgentSpec] = field(default_factory=list)


class TaskDecomposer:
    def decompose(self, task_text: str) -> list[SwarmStage]:
        return [
            SwarmStage("explore", True, [AgentSpec("explorer-1", "explorer", f"Explore context for: {task_text}")]),
            SwarmStage("implement", False, [AgentSpec("implementer-1", "implementer", f"Implement: {task_text}")]),
            SwarmStage("verify", True, [AgentSpec("verifier-1", "verifier", f"Verify: {task_text}")]),
            SwarmStage("audit", False, [AgentSpec("auditor-1", "auditor", f"Audit: {task_text}")]),
        ]


def decompose_development_plan(plan: dict) -> list[dict]:
    """Create fine-grained implementation tasks for Metis adaptation plans."""

    tasks: list[dict] = []
    for phase in plan.get("phases", []):
        phase_id = str(phase.get("id", "phase"))
        for index, surface in enumerate(phase.get("allowed_changes", []), start=1):
            task_id = f"{phase_id}-task-{index:02d}"
            tasks.append(
                {
                    "id": task_id,
                    "phase_id": phase_id,
                    "title": f"Prepare {surface}",
                    "surface": str(surface),
                    "instruction": (
                        f"Work only on {surface}. Preserve Metis core architecture unless the approved plan explicitly "
                        "requires a core change. Keep the change small, reviewable, and testable."
                    ),
                    "verification": _development_task_verification(str(surface)),
                    "status": "pending",
                }
            )
    return tasks


def _development_task_verification(surface: str) -> str:
    lowered = surface.lower()
    if "prompt" in lowered:
        return "Confirm prompt file exists and contains app name, workflow, and evidence rules."
    if "command" in lowered or ".claude" in lowered or ".codex" in lowered:
        return "Confirm slash command file exists and references analysis, approval, decomposition, and verification workflow."
    if "manifest" in lowered:
        return "Confirm manifest JSON exists and contains name, description, workspace, model, profile, and icon_text."
    if "task" in lowered:
        return "Confirm metis-dev-tasks.json exists with small pending tasks and phase ids."
    return "Confirm artifact exists and is referenced by the adaptation plan."
