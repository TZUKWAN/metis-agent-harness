"""Data models for the Behavior Rules Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from metis.quality.gates import GateSpec


@dataclass(frozen=True)
class BehaviorRule:
    """A single behavioral rule internalized from user configuration.

    Rules are classified by *category* so the runtime knows how to apply them:
    - ``prompt``   → injected into the system prompt stack as a PromptLayer
    - ``hook``     → registered on HookBus at a specific event
    - ``gate``     → evaluated during finalization as a quality gate
    - ``contract`` → merged into TaskContractV1 constraints
    """

    id: str
    category: Literal["prompt", "hook", "gate", "contract"]
    priority: int
    enabled: bool
    prompt_text: str = ""
    hook_event: str = ""
    hook_handler: Callable | None = None
    gate_spec: GateSpec | None = None
    contract_field: str = ""
    contract_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "priority": self.priority,
            "enabled": self.enabled,
            "prompt_text": self.prompt_text,
            "hook_event": self.hook_event,
            "contract_field": self.contract_field,
            "contract_value": self.contract_value,
            "gate_name": self.gate_spec.name if self.gate_spec else None,
        }


@dataclass
class BehaviorRulesConfig:
    """Aggregated configuration for all active behavior rules."""

    rules: list[BehaviorRule] = field(default_factory=list)
    auto_audit: bool = True
    audit_agents: list[str] = field(default_factory=list)
    swarm_audit_enabled: bool = True

    def get_prompt_rules(self) -> list[BehaviorRule]:
        return [r for r in self.rules if r.category == "prompt" and r.enabled]

    def get_hook_rules(self) -> list[BehaviorRule]:
        return [r for r in self.rules if r.category == "hook" and r.enabled]

    def get_gate_rules(self) -> list[BehaviorRule]:
        return [r for r in self.rules if r.category == "gate" and r.enabled]

    def get_contract_rules(self) -> list[BehaviorRule]:
        return [r for r in self.rules if r.category == "contract" and r.enabled]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules": [r.to_dict() for r in self.rules],
            "auto_audit": self.auto_audit,
            "audit_agents": self.audit_agents,
            "swarm_audit_enabled": self.swarm_audit_enabled,
        }
