"""Business adapter interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from metis.quality.gates import GateSpec
from metis.swarm.roles import RoleTemplate
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@dataclass
class AdapterRegistration:
    tools: list[str] = field(default_factory=list)
    prompt_fragments: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)


class Adapter:
    name = "adapter"

    def register_tools(self, registry: ToolRegistry) -> list[ToolSpec]:
        return []

    def register_prompt_fragments(self) -> list[str]:
        return []

    def register_quality_gates(self) -> list[GateSpec]:
        return []

    def register_roles(self) -> list[RoleTemplate]:
        return []

    def health_check(self) -> dict[str, Any]:
        return {"name": self.name, "ok": True}

    def register(self, registry: ToolRegistry) -> AdapterRegistration:
        registration = AdapterRegistration()
        for spec in self.register_tools(registry):
            registry.register(spec)
            registration.tools.append(spec.name)
        registration.prompt_fragments.extend(self.register_prompt_fragments())
        registration.quality_gates.extend(spec.name for spec in self.register_quality_gates())
        registration.roles.extend(role.role_id for role in self.register_roles())
        return registration
