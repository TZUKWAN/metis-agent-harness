"""Tool-call guardrails for small-model loops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from metis.runtime.response import ToolCall, ToolResult
from metis.tools.spec import ToolSpec


@dataclass(frozen=True)
class GuardrailDecision:
    action: str
    message: str = ""

    @property
    def blocked(self) -> bool:
        return self.action in {"block", "halt"}


@dataclass
class ToolCallGuardrailController:
    max_exact_failures: int = 2
    max_same_tool_failures: int = 4
    max_mutating_repeats: int = 2
    _failure_counts: dict[str, int] = field(default_factory=dict)
    _tool_failure_counts: dict[str, int] = field(default_factory=dict)
    _mutating_counts: dict[str, int] = field(default_factory=dict)

    def before_call(self, call: ToolCall, spec: ToolSpec) -> GuardrailDecision:
        exact_key = self._exact_key(call)
        mutating_key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
        if self._failure_counts.get(exact_key, 0) >= self.max_exact_failures:
            return GuardrailDecision("block", f"Repeated failed call blocked: {call.name}")
        if self._tool_failure_counts.get(call.name, 0) >= self.max_same_tool_failures:
            return GuardrailDecision("halt", f"Tool failure limit reached: {call.name}")
        if spec.side_effect != "read" and self._mutating_counts.get(mutating_key, 0) >= self.max_mutating_repeats:
            return GuardrailDecision("block", f"Repeated mutating call blocked: {call.name}")
        return GuardrailDecision("allow")

    def after_call(self, call: ToolCall, spec: ToolSpec, result: ToolResult) -> None:
        exact_key = self._exact_key(call)
        if result.failed:
            self._failure_counts[exact_key] = self._failure_counts.get(exact_key, 0) + 1
            self._tool_failure_counts[call.name] = self._tool_failure_counts.get(call.name, 0) + 1
        if spec.side_effect != "read":
            mutating_key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
            self._mutating_counts[mutating_key] = self._mutating_counts.get(mutating_key, 0) + 1

    @staticmethod
    def _exact_key(call: ToolCall) -> str:
        return f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
