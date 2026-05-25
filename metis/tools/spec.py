"""Tool specification primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Protocol


class ToolHandler(Protocol):
    def __call__(self, args: dict[str, Any], context: "ToolContext") -> Any:
        ...


class ToolPermissionLevel(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    SHELL_SAFE = "shell_safe"
    SHELL_DANGEROUS = "shell_dangerous"
    NETWORK = "network"
    CREDENTIAL_ACCESS = "credential_access"
    EXTERNAL_PUBLISH = "external_publish"


@dataclass
class ToolContext:
    session_id: str = "default"
    goal_id: str | None = None
    step_id: str | None = None
    workspace: str = "."
    allowed_tools: list[str] | None = None
    allowed_tool_permissions: list[str] | None = None
    role: str | None = None
    state: Any = None
    artifacts: Any = None
    evidence: Any = None
    hooks: Any = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], Any]
    category: str = "general"
    side_effect: str = "read"
    permission_level: str = ToolPermissionLevel.READ_ONLY.value
    max_result_chars: int | None = None
    allowed_roles: list[str] | None = None
    requires_permission: bool = False
    retry_policy: str = "default"
    verification: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
            "metadata": {
                "category": self.category,
                "side_effect": self.side_effect,
                "permission_level": self.permission_level,
                "requires_permission": self.requires_permission,
            },
        }
