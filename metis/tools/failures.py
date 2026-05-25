"""Structured tool failure taxonomy and repair hints."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ToolFailureType(StrEnum):
    UNKNOWN_TOOL = "unknown_tool"
    TOOL_NOT_ALLOWED = "tool_not_allowed"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    UNSAFE_COMMAND = "unsafe_command"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    HOOK_BLOCKED = "hook_blocked"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    COMMAND_FAILED = "command_failed"
    RUNTIME_ERROR = "runtime_error"


_REPAIR_INSTRUCTIONS: dict[ToolFailureType, str] = {
    ToolFailureType.UNKNOWN_TOOL: (
        "Retry with one of the available tool names exactly as provided by the runtime. "
        "Do not invent tool names."
    ),
    ToolFailureType.TOOL_NOT_ALLOWED: (
        "Use only tools allowed in the current context. If no allowed tool can complete the task, "
        "return a blocked final response explaining the missing capability."
    ),
    ToolFailureType.SCHEMA_VALIDATION_FAILED: (
        "Retry the same tool with corrected arguments that satisfy the provided tool schema. "
        "Do not claim the task is complete until the corrected tool call succeeds."
    ),
    ToolFailureType.POLICY_DENIED: (
        "Do not retry the denied tool call. Choose a safer allowed action, or return blocked if the task "
        "requires the denied action."
    ),
    ToolFailureType.APPROVAL_REQUIRED: (
        "Do not bypass approval. Return blocked or wait for an approval workflow before attempting this action."
    ),
    ToolFailureType.UNSAFE_COMMAND: (
        "Do not retry this command or a disguised equivalent. Use a non-destructive alternative if one exists."
    ),
    ToolFailureType.GUARDRAIL_BLOCKED: (
        "Do not repeat the same failing tool call. Change the approach or return blocked if progress is impossible."
    ),
    ToolFailureType.HOOK_BLOCKED: (
        "Respect the runtime hook block. Change the approach only if a clearly allowed alternative exists."
    ),
    ToolFailureType.RETRY_BUDGET_EXHAUSTED: (
        "Retry budget is exhausted for this tool call pattern. Do not repeat it; choose a different allowed "
        "approach or return blocked."
    ),
    ToolFailureType.COMMAND_FAILED: (
        "Inspect the command output, fix the command or inputs, and retry only if the next attempt is materially different."
    ),
    ToolFailureType.RUNTIME_ERROR: (
        "Inspect the runtime error, adjust the tool arguments or prerequisite state, and retry only with a corrected call."
    ),
}

_RECOVERABLE: dict[ToolFailureType, bool] = {
    ToolFailureType.UNKNOWN_TOOL: True,
    ToolFailureType.TOOL_NOT_ALLOWED: True,
    ToolFailureType.SCHEMA_VALIDATION_FAILED: True,
    ToolFailureType.POLICY_DENIED: False,
    ToolFailureType.APPROVAL_REQUIRED: False,
    ToolFailureType.UNSAFE_COMMAND: False,
    ToolFailureType.GUARDRAIL_BLOCKED: False,
    ToolFailureType.HOOK_BLOCKED: False,
    ToolFailureType.RETRY_BUDGET_EXHAUSTED: False,
    ToolFailureType.COMMAND_FAILED: True,
    ToolFailureType.RUNTIME_ERROR: True,
}


def tool_failure_metadata(
    failure_type: ToolFailureType,
    *,
    retry_allowed: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recoverable = _RECOVERABLE[failure_type]
    metadata: dict[str, Any] = {
        "failure_type": failure_type.value,
        "recoverable": recoverable,
        "retry_allowed": recoverable if retry_allowed is None else retry_allowed,
        "repair_instruction": _REPAIR_INSTRUCTIONS[failure_type],
    }
    if extra:
        metadata.update(extra)
    return metadata
