"""Role templates for swarm agents."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoleTemplate:
    role_id: str
    mission: str
    allowed_tools: list[str] = field(default_factory=list)


class RoleTemplateBank:
    def __init__(self) -> None:
        self._roles = {
            "planner": RoleTemplate("planner", "Break goals into executable steps", ["read_file"]),
            "explorer": RoleTemplate("explorer", "Inspect files and gather evidence", ["read_file", "run_shell"]),
            "implementer": RoleTemplate("implementer", "Modify files to complete assigned work", ["read_file", "write_file", "run_shell"]),
            "verifier": RoleTemplate("verifier", "Run checks and verify outcomes", ["read_file", "run_shell"]),
            "auditor": RoleTemplate("auditor", "Audit truthfulness, evidence, and artifacts", ["read_file", "run_shell"]),
            "synthesizer": RoleTemplate("synthesizer", "Synthesize audited results into final output", ["read_file", "write_file"]),
        }

    def get(self, role_id: str) -> RoleTemplate:
        try:
            return self._roles[role_id]
        except KeyError as exc:
            raise KeyError(f"Unknown role: {role_id}") from exc

    def list_roles(self) -> list[RoleTemplate]:
        return [self._roles[key] for key in sorted(self._roles)]
