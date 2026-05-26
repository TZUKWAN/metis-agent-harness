"""Tool dispatching with hook integration."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from metis.config import TOOL_EXECUTION_TIMEOUT
from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.runtime.response import ToolCall, ToolResult
from metis.tools.failures import ToolFailureType, tool_failure_metadata
from metis.tools.guardrails import ToolCallGuardrailController
from metis.tools.policy import ToolPolicyEngine
from metis.tools.registry import ToolRegistry
from metis.tools.result_store import ToolResultStore
from metis.tools.schema_feedback import schema_repair_feedback
from metis.tools.schema_validator import ToolArgumentSchemaValidator
from metis.tools.analytics import ToolAnalytics
from metis.tools.coerce import coerce_arguments
from metis.tools.sanitizer import ToolInputSanitizer
from metis.tools.spec import ToolContext

_executor = ThreadPoolExecutor(max_workers=4)


class ToolDispatcher:
    def __init__(
        self,
        registry: ToolRegistry,
        hooks: HookBus | None = None,
        result_store: ToolResultStore | None = None,
        guardrails: ToolCallGuardrailController | None = None,
        policy_engine: ToolPolicyEngine | None = None,
        schema_validator: ToolArgumentSchemaValidator | None = None,
    ) -> None:
        self.registry = registry
        self.hooks = hooks or HookBus()
        self.result_store = result_store
        self.guardrails = guardrails
        self.policy_engine = policy_engine or ToolPolicyEngine()
        self.schema_validator = schema_validator or ToolArgumentSchemaValidator()
        self.sanitizer = ToolInputSanitizer()
        self.analytics = ToolAnalytics()

    def dispatch(self, call: ToolCall, context: ToolContext | None = None) -> ToolResult:
        context = context or ToolContext()
        start = time.monotonic()
        context.hooks = context.hooks or self.hooks

        call = ToolCall(
            id=call.id,
            name=call.name,
            arguments=self.sanitizer.sanitize(call.arguments),
        )

        spec = self.registry.get(call.name)
        if spec is None:
            error = f"Unknown tool: {call.name}"
            return ToolResult(
                call.name,
                self._json_error(error),
                status="error",
                tool_call_id=call.id,
                error=error,
                metadata=tool_failure_metadata(ToolFailureType.UNKNOWN_TOOL),
            )

        policy_decision = self.policy_engine.before_dispatch(call, spec, context)
        if not policy_decision.allowed:
            error = policy_decision.reason or f"Tool policy denied call: {call.name}"
            self.hooks.emit(
                EventType.TOOL_GUARDRAIL_BLOCK,
                {
                    "tool": call.name,
                    "tool_call_id": call.id,
                    "message": error,
                    "policy_decision": policy_decision.action,
                    "risk_level": policy_decision.risk_level,
                },
            )
            return ToolResult(
                call.name,
                self._json_error(error),
                status="blocked",
                tool_call_id=call.id,
                error=error,
                metadata={
                    **tool_failure_metadata(self._policy_failure_type(policy_decision.action, error)),
                    "policy_decision": policy_decision.action,
                    "risk_level": policy_decision.risk_level,
                    **policy_decision.metadata,
                },
            )

        if self.guardrails is not None:
            decision = self.guardrails.before_call(call, spec)
            if decision.blocked:
                self.hooks.emit(
                    EventType.TOOL_GUARDRAIL_BLOCK,
                    {"tool": call.name, "tool_call_id": call.id, "message": decision.message},
                )
                return ToolResult(
                    call.name,
                    self._json_error(decision.message),
                    status="blocked",
                    tool_call_id=call.id,
                    error=decision.message,
                    metadata=tool_failure_metadata(ToolFailureType.GUARDRAIL_BLOCKED, retry_allowed=False),
                )

        coerced_args = coerce_arguments(spec.parameters, call.arguments)
        schema_result = self.schema_validator.validate(spec.parameters, coerced_args)
        if schema_result.passed and coerced_args != call.arguments:
            call = ToolCall(id=call.id, name=call.name, arguments=coerced_args)
        if not schema_result.passed:
            error = "Tool argument schema validation failed: " + "; ".join(schema_result.errors)
            schema_feedback = schema_repair_feedback(schema_result.errors)
            self.hooks.emit(
                EventType.TOOL_GUARDRAIL_BLOCK,
                {
                    "tool": call.name,
                    "tool_call_id": call.id,
                    "message": error,
                    "schema_errors": schema_result.errors,
                },
            )
            return ToolResult(
                call.name,
                self._json_error(error),
                status="blocked",
                tool_call_id=call.id,
                error=error,
                metadata={
                    **tool_failure_metadata(ToolFailureType.SCHEMA_VALIDATION_FAILED),
                    "policy_decision": policy_decision.action,
                    "risk_level": policy_decision.risk_level,
                    "schema_valid": False,
                    "schema_errors": schema_result.errors,
                    "schema_repair_hints": schema_feedback["hints"],
                    "schema_repair_hint_types": schema_feedback["hint_types"],
                    "schema_repair_hint_details": schema_feedback["details"],
                },
            )

        pre_ctx = self.hooks.emit(
            EventType.TOOL_PRE_DISPATCH,
            {"tool": call.name, "args": call.arguments, "tool_call_id": call.id},
        )
        if pre_ctx.get("blocked"):
            reason = str(pre_ctx.get("block_reason", "Blocked by hook"))
            return ToolResult(
                call.name,
                self._json_error(reason),
                status="blocked",
                tool_call_id=call.id,
                error=reason,
                metadata=tool_failure_metadata(ToolFailureType.HOOK_BLOCKED, retry_allowed=False),
            )

        try:
            future = _executor.submit(spec.handler, call.arguments, context)
            effective_timeout = spec.timeout_seconds or TOOL_EXECUTION_TIMEOUT
            try:
                raw_result = future.result(timeout=effective_timeout)
            except FuturesTimeoutError:
                error = f"Tool '{call.name}' timed out after {effective_timeout}s"
                return ToolResult(
                    call.name,
                    self._json_error(error),
                    status="error",
                    tool_call_id=call.id,
                    error=error,
                    metadata=tool_failure_metadata(ToolFailureType.RUNTIME_ERROR, extra={"timeout": True}),
                )
            content = raw_result if isinstance(raw_result, str) else json.dumps(raw_result, ensure_ascii=False)
            status = "ok"
            error_text = None
            if isinstance(raw_result, dict) and "exit_code" in raw_result and raw_result.get("exit_code") != 0:
                status = "error"
                error_text = f"Command failed with exit_code={raw_result.get('exit_code')}"
            metadata: dict[str, Any] = {
                "policy_decision": policy_decision.action,
                "risk_level": policy_decision.risk_level,
                "schema_valid": True,
            }
            if status == "error":
                metadata.update(tool_failure_metadata(ToolFailureType.COMMAND_FAILED))
            if isinstance(raw_result, dict):
                for key in ("exit_code", "command", "command_text", "passed", "test_framework"):
                    if key in raw_result:
                        metadata[key] = raw_result[key]
            if self.result_store is not None:
                persisted = self.result_store.maybe_persist(
                    content=content,
                    tool_name=call.name,
                    tool_call_id=call.id,
                    threshold=spec.max_result_chars,
                )
                content = persisted.content
                metadata.update(
                    {
                        "persisted": persisted.persisted,
                        "persisted_path": persisted.path,
                        "original_size": persisted.original_size,
                        "checksum": persisted.checksum,
                    }
                )
                if persisted.persisted:
                    self.hooks.emit(
                        EventType.TOOL_RESULT_PERSISTED,
                        {
                            "tool": call.name,
                            "tool_call_id": call.id,
                            "path": persisted.path,
                            "original_size": persisted.original_size,
                            "checksum": persisted.checksum,
                        },
                    )
            metadata["dispatch_duration_ms"] = round((time.monotonic() - start) * 1000, 1)
            metadata["result_size_bytes"] = len(content.encode("utf-8")) if content else 0
            result = ToolResult(call.name, content, status=status, tool_call_id=call.id, error=error_text, metadata=metadata)
            if self.guardrails is not None:
                self.guardrails.after_call(call, spec, result)
            self.hooks.emit(
                EventType.TOOL_POST_DISPATCH,
                {"tool": call.name, "args": call.arguments, "result": content, "tool_call_id": call.id},
            )
            self.hooks.emit(
                "tool.analytics",
                {
                    "tool": call.name,
                    "category": spec.category,
                    "side_effect": spec.side_effect,
                    "status": status,
                    "duration_ms": metadata["dispatch_duration_ms"],
                    "result_size_bytes": metadata["result_size_bytes"],
                },
            )
            self.analytics.record(call.name, spec.category, metadata["dispatch_duration_ms"], status)
            return result
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            category = spec.category if spec is not None else "unknown"
            self.analytics.record(call.name, category, duration_ms, "error")
            result = ToolResult(
                call.name,
                self._json_error(error),
                status="error",
                tool_call_id=call.id,
                error=error,
                metadata=tool_failure_metadata(
                    ToolFailureType.RUNTIME_ERROR,
                    extra={"exception_type": type(exc).__name__},
                ),
            )
            if self.guardrails is not None:
                self.guardrails.after_call(call, spec, result)
            self.hooks.emit(
                EventType.TOOL_ERROR,
                {"tool": call.name, "args": call.arguments, "error": str(exc), "error_type": type(exc).__name__},
            )
            return result

    @staticmethod
    def _json_error(message: str) -> str:
        return json.dumps({"error": message}, ensure_ascii=False)

    @staticmethod
    def _policy_failure_type(action: str, error: str) -> ToolFailureType:
        lowered = error.lower()
        if action == "approval_required":
            return ToolFailureType.APPROVAL_REQUIRED
        if "dangerous shell command" in lowered or "denied dangerous" in lowered:
            return ToolFailureType.UNSAFE_COMMAND
        if "not allowed" in lowered:
            return ToolFailureType.TOOL_NOT_ALLOWED
        return ToolFailureType.POLICY_DENIED
