"""Configurable approval rules for the HITL system."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from metis.tools.spec import ToolSpec


@dataclass
class ApprovalRule:
    """A rule that determines whether a tool call requires human approval."""

    name: str
    description: str = ""
    # If set, only match tools with these names
    tool_names: list[str] | None = None
    # If set, only match tools with these permission levels
    permission_levels: list[str] | None = None
    # If set, only match tools with these side effects
    side_effects: list[str] | None = None
    # If set, match tools whose name matches any of these regex patterns
    name_patterns: list[str] | None = None
    # Custom matcher function
    matcher: Callable[[str, dict[str, Any], ToolSpec | None], bool] | None = None

    def matches(self, tool_name: str, arguments: dict[str, Any], spec: ToolSpec | None) -> bool:
        """Check if this rule matches a tool call."""
        if self.matcher is not None:
            return self.matcher(tool_name, arguments, spec)

        has_criteria = False

        if self.tool_names is not None:
            has_criteria = True
            if tool_name not in self.tool_names:
                return False

        if self.permission_levels is not None:
            if spec is None:
                return False
            has_criteria = True
            if spec.permission_level not in self.permission_levels:
                return False
        if self.side_effects is not None:
            if spec is None:
                return False
            has_criteria = True
            if spec.side_effect not in self.side_effects:
                return False

        if self.name_patterns is not None:
            has_criteria = True
            if not any(re.search(pattern, tool_name) for pattern in self.name_patterns):
                return False

        # If we have criteria and all matched, or no criteria (catch-all), return True
        return True


def default_approval_rules() -> list[ApprovalRule]:
    """Return the default set of approval rules for v0.2.0.

    Destructive, credential, and external-publish operations always require approval.
    Workspace write operations require approval by default.
    """
    return [
        ApprovalRule(
            name="destructive_side_effects",
            description="Tools with destructive side effects always require approval",
            side_effects=["destructive"],
        ),
        ApprovalRule(
            name="credential_access",
            description="Tools accessing credentials always require approval",
            permission_levels=["credential_access"],
        ),
        ApprovalRule(
            name="external_publish",
            description="Tools that publish externally always require approval",
            permission_levels=["external_publish"],
        ),
        ApprovalRule(
            name="shell_dangerous",
            description="Dangerous shell commands always require approval",
            permission_levels=["shell_dangerous"],
        ),
        ApprovalRule(
            name="network_operations",
            description="Network operations always require approval",
            side_effects=["network"],
        ),
    ]
