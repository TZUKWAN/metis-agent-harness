"""Planning dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Goal:
    id: str
    session_id: str
    objective: str
    status: str = "active"
    acceptance_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Plan:
    id: str
    goal_id: str
    version: int = 1
    status: str = "active"
    created_at: str = ""


@dataclass
class Step:
    id: str
    plan_id: str
    order_index: int
    title: str
    action: str
    expected_output: str
    verification_method: str
    done_condition: str
    status: str = "pending"
    required_inputs: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    required_gates: list[str] = field(default_factory=list)
