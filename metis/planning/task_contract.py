"""Task contract prompt fragments for controlled execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from metis.planning.models import Goal, Step


@dataclass(frozen=True)
class TaskContractV1:
    """Structured intake contract shared by Metis runtime entry points."""

    objective: str
    scope: str = "workspace task"
    non_goals: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    artifact_requirements: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    approval_required: bool = False
    completion_definition: str = "The task is complete only when requested deliverables are produced and verified with evidence."
    source: str = "runtime_intake"
    version: str = "task-contract-v1"
    testing_required: bool = True
    audit_required: bool = True
    research_required: bool = False
    subtasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def stable_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def contract_hash(self) -> str:
        return hashlib.sha256(self.stable_json().encode("utf-8")).hexdigest()

    def to_prompt(self) -> str:
        lines = [
            "[Metis task contract v1]",
            f"Contract hash: {self.contract_hash()}",
            f"Objective: {self.objective}",
            f"Scope: {self.scope}",
            f"Approval required: {str(self.approval_required).lower()}",
            f"Testing required: {str(self.testing_required).lower()}",
            f"Audit required: {str(self.audit_required).lower()}",
            f"Research required: {str(self.research_required).lower()}",
            "",
            "Deliverables:",
            *self._bullets(self.deliverables),
            "",
            "Acceptance criteria:",
            *self._bullets(self.acceptance_criteria),
            "",
            "Evidence requirements:",
            *self._bullets(self.evidence_requirements),
            "",
            "Artifact requirements:",
            *self._bullets(self.artifact_requirements),
            "",
            "Verification commands:",
            *self._bullets(self.verification_commands),
            "",
            "Allowed tools:",
            *self._bullets(self.allowed_tools),
            "",
            "Forbidden actions:",
            *self._bullets(self.forbidden_actions),
            "",
            "Completion definition:",
            self.completion_definition,
            "",
            "Rules:",
            "- Do not claim completion until the contract acceptance criteria are satisfied.",
            "- Do not invent files, tests, data, uploads, API calls, tool outputs, or evidence.",
            "- If evidence is missing, report the missing evidence instead of claiming completion.",
        ]
        if self.non_goals:
            lines.extend(["", "Non-goals:", *self._bullets(self.non_goals)])
        if self.risk_flags:
            lines.extend(["", "Risk flags:", *self._bullets(self.risk_flags)])
        return "\n".join(lines)

    @staticmethod
    def _bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] if items else ["- (none specified)"]


def build_intake_task_contract(
    objective: str,
    *,
    allowed_tools: list[str] | None = None,
    source: str = "runtime_intake",
) -> TaskContractV1:
    """Create a conservative task contract from a natural-language request."""

    objective = objective.strip()
    if not objective:
        raise ValueError("task objective is required")
    return TaskContractV1(
        objective=objective,
        deliverables=["Satisfy the user request with concrete, reviewable output."],
        acceptance_criteria=[
            "The response directly addresses the requested objective.",
            "Any claim of completion is backed by evidence from files, tool results, commands, or artifacts.",
            "Known missing work, unverified assumptions, and residual risks are reported truthfully.",
            "Testing and verification are part of the default task scope unless explicitly excluded.",
            "All sub-tasks have been addressed with concrete evidence.",
        ],
        allowed_tools=list(allowed_tools or []),
        forbidden_actions=[
            "Do not fabricate command output, files, uploads, API calls, tests, or external research.",
            "Do not modify files outside the active workspace unless explicitly approved.",
            "Do not claim completion without concrete evidence.",
            "Do not use placeholder text, mock data, or simulated results.",
        ],
        evidence_requirements=[
            "Use concrete tool results, file paths, command outputs, artifacts, or trace events for completion claims.",
            "For tests, record the exact command and result.",
            "For generated files, ensure the file exists at the reported path.",
            "If external research is needed, record search queries and sources.",
        ],
        artifact_requirements=["Artifacts must use portable workspace-relative paths when possible."],
        verification_commands=[],
        source=source,
        testing_required=True,
        audit_required=True,
    )


def build_task_contract(
    goal: Goal,
    step: Step,
    *,
    allowed_tools: list[str] | None = None,
    model_profile: str = "small",
) -> str:
    """Build a model-facing contract for exactly one current step."""
    tools = allowed_tools if allowed_tools is not None else step.allowed_tools
    if model_profile == "small":
        return "\n".join(
            [
                "[Metis controlled execution contract]",
                "Execute exactly one step. Do not skip ahead.",
                "",
                f"Goal: {goal.objective}",
                f"Current step: {step.title}",
                f"Action: {step.action}",
                f"Expected output: {step.expected_output}",
                f"Verification method: {step.verification_method}",
                f"Done condition: {step.done_condition}",
                f"Allowed tools: {', '.join(tools) if tools else '(none)'}",
                "",
                "Rules:",
                "- If a tool is required, call exactly one allowed tool.",
                "- Do not claim completion until the done condition is verified.",
                "- Do not invent files, tests, data, tool outputs, or evidence.",
                "- If blocked, say exactly what evidence or input is missing.",
            ]
        )

    return "\n".join(
        [
            "[Metis controlled execution contract]",
            f"Goal: {goal.objective}",
            f"Acceptance criteria: {', '.join(goal.acceptance_criteria) or '(none specified)'}",
            f"Constraints: {', '.join(goal.constraints) or '(none specified)'}",
            "",
            f"Current step {step.order_index}: {step.title}",
            f"Action: {step.action}",
            f"Required inputs: {', '.join(step.required_inputs) or '(none)'}",
            f"Expected output: {step.expected_output}",
            f"Allowed tools: {', '.join(tools) if tools else '(none)'}",
            f"Verification method: {step.verification_method}",
            f"Done condition: {step.done_condition}",
        ]
    )
