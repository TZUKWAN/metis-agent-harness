"""Plugin extension API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from metis.quality.gates import GateSpec
from metis.swarm.roles import RoleTemplate
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str = "0.1.0"
    entrypoint: str = "plugin.py"
    description: str = ""
    tools: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    eval_suites: tuple[str, ...] = ()
    prompt_fragments: tuple[str, ...] = ()
    evidence_requirements: tuple[str, ...] = ()
    uninstall_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "tools",
            "required_permissions",
            "eval_suites",
            "prompt_fragments",
            "evidence_requirements",
            "uninstall_paths",
        ):
            data[key] = list(data[key])
        return data


@dataclass
class PluginContext:
    tool_registry: ToolRegistry
    prompt_fragments: list[str] = field(default_factory=list)
    quality_gates: dict[str, GateSpec] = field(default_factory=dict)
    role_templates: dict[str, RoleTemplate] = field(default_factory=dict)
    artifact_validators: dict[str, Any] = field(default_factory=dict)

    def register_tool(self, spec: ToolSpec) -> None:
        self.tool_registry.register(spec)

    def register_prompt_fragment(self, text: str) -> None:
        self.prompt_fragments.append(text)

    def register_quality_gate(self, spec: GateSpec) -> None:
        self.quality_gates[spec.name] = spec

    def register_role_template(self, role: RoleTemplate) -> None:
        self.role_templates[role.role_id] = role
