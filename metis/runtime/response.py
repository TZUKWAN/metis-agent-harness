"""Shared runtime dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = ""
    raw: Any = None


@dataclass
class ToolResult:
    tool_name: str
    content: str
    status: str = "ok"
    tool_call_id: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status != "ok" or self.error is not None


@dataclass
class NormalizedResponse:
    content: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass
class AgentRunRequest:
    messages: list[dict[str, Any]]
    max_turns: int = 20
    session_id: str = "default"
    allowed_tools: list[str] | None = None
    allowed_tool_permissions: list[str] | None = None
    task_contract_hash: str = ""
    prompt_stack_hash: str = ""
    resume_from_checkpoint: bool = False


@dataclass
class AgentRunResult:
    status: str
    final_text: str = ""
    final_verified: bool = False
    messages: list[dict[str, Any]] = field(default_factory=list)
    turns_used: int = 0
    tool_results: list[ToolResult] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
