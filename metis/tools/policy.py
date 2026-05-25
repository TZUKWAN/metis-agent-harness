"""Runtime tool policy checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from metis.runtime.response import ToolCall
from metis.tools.spec import ToolContext, ToolSpec


class ToolRiskLevel(StrEnum):
    SAFE_READ = "safe_read"
    WORKSPACE_WRITE = "workspace_write"
    EXECUTE = "execute"
    NETWORK = "network"
    CREDENTIAL = "credential"
    DESTRUCTIVE = "destructive"
    EXTERNAL_PUBLISH = "external_publish"


@dataclass(frozen=True)
class ToolPolicyDecision:
    action: str
    reason: str = ""
    risk_level: str = ToolRiskLevel.SAFE_READ.value
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.action == "allow"

    @property
    def blocked(self) -> bool:
        return self.action in {"block", "deny"}

    @property
    def approval_required(self) -> bool:
        return self.action == "approval_required"


@dataclass(frozen=True)
class ToolPolicy:
    deny_shell_patterns: tuple[str, ...] = (
        r"\brm\s+-rf\b",
        r"\bdel\s+/[fsq]\b",
        r"\brmdir\s+/s\b",
        r"\bformat\b",
        r"\bshutdown\b",
        r"\breg\s+(add|delete)\b",
        r"\bsetx\b",
        r"\bcurl\b.*\|\s*(sh|bash|powershell|pwsh)",
        r"\biwr\b.*\|\s*(iex|powershell|pwsh)",
        r"\binvoke-webrequest\b.*\|\s*(iex|powershell|pwsh)",
    )
    approval_shell_patterns: tuple[str, ...] = (
        r"\bgit\s+push\b",
        r"\bgh\s+release\b",
        r"\btwine\s+upload\b",
        r"\bnpm\s+publish\b",
    )
    network_shell_patterns: tuple[str, ...] = (
        r"\bcurl\b",
        r"\bwget\b",
        r"\binvoke-webrequest\b",
        r"\biwr\b",
    )


class CommandClassifier:
    def __init__(self, policy: ToolPolicy | None = None) -> None:
        self.policy = policy or ToolPolicy()

    def classify(self, command: str) -> ToolPolicyDecision:
        normalized = command.lower()
        for pattern in self.policy.deny_shell_patterns:
            if re.search(pattern, normalized):
                return ToolPolicyDecision(
                    "block",
                    f"Denied dangerous shell command pattern: {pattern}",
                    ToolRiskLevel.DESTRUCTIVE.value,
                    {"pattern": pattern},
                )
        for pattern in self.policy.approval_shell_patterns:
            if re.search(pattern, normalized):
                return ToolPolicyDecision(
                    "approval_required",
                    f"Shell command requires approval: {pattern}",
                    ToolRiskLevel.EXTERNAL_PUBLISH.value,
                    {"pattern": pattern},
                )
        for pattern in self.policy.network_shell_patterns:
            if re.search(pattern, normalized):
                return ToolPolicyDecision(
                    "approval_required",
                    f"Network shell command requires approval: {pattern}",
                    ToolRiskLevel.NETWORK.value,
                    {"pattern": pattern},
                )
        return ToolPolicyDecision("allow", risk_level=ToolRiskLevel.EXECUTE.value)


class ToolPolicyEngine:
    def __init__(self, policy: ToolPolicy | None = None, command_classifier: CommandClassifier | None = None) -> None:
        self.policy = policy or ToolPolicy()
        self.command_classifier = command_classifier or CommandClassifier(self.policy)

    def before_dispatch(self, call: ToolCall, spec: ToolSpec, context: ToolContext) -> ToolPolicyDecision:
        if context.allowed_tools is not None and call.name not in set(context.allowed_tools):
            return ToolPolicyDecision("block", f"Tool not allowed in current context: {call.name}")
        if context.allowed_tool_permissions is not None and spec.permission_level not in set(context.allowed_tool_permissions):
            return ToolPolicyDecision(
                "block",
                f"Tool permission not allowed in current context: {spec.permission_level}",
                self._risk_from_spec(spec),
                {"permission_level": spec.permission_level},
            )
        if spec.allowed_roles is not None and context.role is not None and context.role not in spec.allowed_roles:
            return ToolPolicyDecision("block", f"Tool not allowed for role {context.role}: {call.name}")
        if call.name in {"run_shell", "run_command", "run_test"}:
            command = self._command_text(call.arguments.get("command", ""))
            return self.command_classifier.classify(command)
        if spec.requires_permission:
            return ToolPolicyDecision(
                "approval_required",
                f"Tool requires approval: {call.name}",
                self._risk_from_spec(spec),
            )
        return ToolPolicyDecision("allow", risk_level=self._risk_from_spec(spec))

    @staticmethod
    def _command_text(command: Any) -> str:
        if isinstance(command, list):
            return " ".join(str(item) for item in command)
        return str(command)

    @staticmethod
    def _risk_from_spec(spec: ToolSpec) -> str:
        metadata_risk = spec.metadata.get("risk_level")
        if metadata_risk:
            return str(metadata_risk)
        if spec.permission_level in {"read_only"}:
            return ToolRiskLevel.SAFE_READ.value
        if spec.permission_level in {"workspace_write"}:
            return ToolRiskLevel.WORKSPACE_WRITE.value
        if spec.permission_level in {"shell_safe", "shell_dangerous"}:
            return ToolRiskLevel.EXECUTE.value
        if spec.permission_level == "network":
            return ToolRiskLevel.NETWORK.value
        if spec.permission_level == "credential_access":
            return ToolRiskLevel.CREDENTIAL.value
        if spec.permission_level == "external_publish":
            return ToolRiskLevel.EXTERNAL_PUBLISH.value
        if spec.side_effect == "read":
            return ToolRiskLevel.SAFE_READ.value
        if spec.side_effect == "write":
            return ToolRiskLevel.WORKSPACE_WRITE.value
        if spec.side_effect == "network":
            return ToolRiskLevel.NETWORK.value
        if spec.side_effect == "destructive":
            return ToolRiskLevel.DESTRUCTIVE.value
        return ToolRiskLevel.EXECUTE.value
