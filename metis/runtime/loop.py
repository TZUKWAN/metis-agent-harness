"""Minimal multi-turn agent loop."""

from __future__ import annotations

import json
import shlex
from typing import Any

from metis.context.engine import ContextEngine
from metis.evidence.extractor import ToolEvidenceExtractor
from metis.evidence.resolver import EvidenceResolver
from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.providers.base import BaseProvider
from metis.runtime.budgets import BudgetConfig
from metis.runtime.errors import ParserError
from metis.runtime.finalization import FinalizationGuard
from metis.runtime.profiles import ModelProfile, get_model_profile
from metis.runtime.response import AgentRunRequest, AgentRunResult, ToolCall, ToolResult
from metis.runtime.status import RuntimeStatus
from metis.runtime.strict_output import StrictOutputParser
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.failures import ToolFailureType, tool_failure_metadata
from metis.tools.guardrails import ToolCallGuardrailController
from metis.providers.parsers.repair import ParserChain
from metis.tools.registry import ToolRegistry
from metis.tools.result_store import ToolResultStore
from metis.tools.schema_feedback import schema_repair_feedback
from metis.tools.spec import ToolContext
from metis.tools.tool_router import ToolRouteRequest, ToolRouter


class AgentLoop:
    """Execute model calls and tool calls until a final response or max_turns."""

    def __init__(
        self,
        *,
        provider: BaseProvider,
        registry: ToolRegistry,
        dispatcher: ToolDispatcher | None = None,
        hooks: HookBus | None = None,
        workspace: str = ".",
        state: Any = None,
        budget: BudgetConfig | None = None,
        profile: str | ModelProfile = "small",
        context_engine: ContextEngine | None = None,
        result_store: ToolResultStore | None = None,
        tool_router: ToolRouter | None = None,
        tool_call_parser: Any = None,
        strict_output_parser: StrictOutputParser | None = None,
        finalization_guard: FinalizationGuard | None = None,
        artifact_store: Any = None,
        evidence_ledger: Any = None,
        evidence_extractor: ToolEvidenceExtractor | None = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.hooks = hooks or HookBus()
        self.profile = get_model_profile(profile)
        self.budget = budget or self.profile.budget
        self.result_store = result_store or ToolResultStore(workspace, self.budget)
        self.dispatcher = dispatcher or ToolDispatcher(
            registry,
            self.hooks,
            self.result_store,
            ToolCallGuardrailController() if self.profile.name == "small" else None,
        )
        self.context_engine = context_engine or ContextEngine(budget=self.budget)
        self.tool_router = tool_router or ToolRouter(registry)
        self.tool_call_parser = tool_call_parser or ParserChain()
        self.strict_output_parser = strict_output_parser or StrictOutputParser()
        self.finalization_guard = finalization_guard or FinalizationGuard(
            evidence_resolver=EvidenceResolver(state=state, artifact_store=artifact_store)
            if state is not None or artifact_store is not None
            else None,
            require_done_evidence_refs=self.profile.require_done_evidence_refs,
        )
        self.artifact_store = artifact_store
        self.evidence_ledger = evidence_ledger
        self.evidence_extractor = evidence_extractor or ToolEvidenceExtractor()
        self.workspace = workspace
        self.state = state

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        messages = list(request.messages)
        all_tool_results: list[ToolResult] = []
        usage_totals: dict[str, int] = {}
        errors: list[str] = []
        trace_events: list[dict[str, Any]] = []
        repair_failure_counts: dict[tuple[str, str], int] = {}
        exhausted_retry_fingerprints: dict[tuple[str, str], str] = {}
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str] = {}

        self._record_trace_event(
            trace_events,
            "agent.start",
            request.session_id,
            status="started",
            attributes={
                "max_turns": request.max_turns,
                "profile": self.profile.name,
                "task_contract_hash": request.task_contract_hash,
                "prompt_stack_hash": request.prompt_stack_hash,
                "allowed_tool_permissions": request.allowed_tool_permissions or [],
                "resume_from_checkpoint": request.resume_from_checkpoint,
            },
        )
        self.hooks.emit(EventType.AGENT_PRE_RUN, {"session_id": request.session_id})
        if self.state is not None:
            self.state.create_session(request.session_id)
            self._record_checkpoint(
                request.session_id,
                phase="agent.resume" if request.resume_from_checkpoint else "agent.start",
                status="resumed" if request.resume_from_checkpoint else "started",
                task_contract_hash=request.task_contract_hash,
                prompt_stack_hash=request.prompt_stack_hash,
                metadata={"max_turns": request.max_turns, "profile": self.profile.name},
            )
            if not request.resume_from_checkpoint:
                for message in messages:
                    if message.get("role") in {"system", "user", "assistant", "tool"}:
                        self.state.append_message(
                            request.session_id,
                            str(message.get("role", "")),
                            str(message.get("content", "")),
                            {"source": "initial"},
                        )

        try:
            for turn_index in range(request.max_turns):
                tool_schemas = self.tool_router.schemas(
                    ToolRouteRequest(stage="execute", allowed_tools=request.allowed_tools, profile=self.profile)
                )

                self.hooks.emit(
                    EventType.MODEL_PRE_CALL,
                    {"session_id": request.session_id, "turn": turn_index + 1, "tool_count": len(tool_schemas)},
                )
                context_result = self.context_engine.build(messages)
                self._record_trace_event(
                    trace_events,
                    "model.request",
                    request.session_id,
                    turn=turn_index + 1,
                    status="started",
                    attributes={
                        "message_count": len(context_result.messages),
                        "tool_count": len(tool_schemas),
                        "compressed": context_result.compressed,
                        "gen_ai.operation.name": "chat",
                    },
                )
                if context_result.compressed:
                    self.hooks.emit(
                        "context.compressed",
                        {
                            "session_id": request.session_id,
                            "turn": turn_index + 1,
                            "original_chars": context_result.original_chars,
                            "final_chars": context_result.final_chars,
                            "max_chars": context_result.max_chars,
                        },
                    )
                response = await self.provider.complete(context_result.messages, tools=tool_schemas)
                self._record_trace_event(
                    trace_events,
                    "model.response",
                    request.session_id,
                    turn=turn_index + 1,
                    status="ok",
                    attributes={
                        "tool_call_count": len(response.tool_calls),
                        "finish_reason": response.finish_reason,
                        "usage": response.usage,
                        "gen_ai.operation.name": "chat",
                    },
                )
                if self.tool_call_parser is not None and not response.tool_calls:
                    raw_to_parse = response.raw if isinstance(response.raw, str) else response.content
                    response.tool_calls = await self._parse_tool_calls_with_repair(
                        raw_to_parse,
                        context_result.messages,
                        tool_schemas,
                        errors,
                        trace_events,
                        request.session_id,
                        turn_index + 1,
                    )
                self.hooks.emit(
                    EventType.MODEL_POST_CALL,
                    {"session_id": request.session_id, "turn": turn_index + 1, "usage": response.usage},
                )
                self._merge_usage(usage_totals, response.usage)

                if response.tool_calls and (
                    len(response.tool_calls) > self.profile.max_tool_calls_per_turn
                    or (self.profile.one_tool_call_per_turn and len(response.tool_calls) > 1)
                ):
                    reason = (
                        f"Tool call limit exceeded: got {len(response.tool_calls)}, "
                        f"max={1 if self.profile.one_tool_call_per_turn else self.profile.max_tool_calls_per_turn}"
                    )
                    result = AgentRunResult(
                        status=RuntimeStatus.BLOCKED.value,
                        final_text="",
                        messages=messages,
                        turns_used=turn_index + 1,
                        tool_results=all_tool_results,
                        usage=usage_totals,
                        errors=errors + [reason],
                        trace_events=trace_events,
                    )
                    self.hooks.emit(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
                    self._record_checkpoint(
                        request.session_id,
                        phase="agent.finalization",
                        status=result.status,
                        task_contract_hash=request.task_contract_hash,
                        prompt_stack_hash=request.prompt_stack_hash,
                        metadata={"turns_used": result.turns_used, "error_count": len(result.errors)},
                    )
                    return result

                assistant_message: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
                if response.tool_calls:
                    assistant_message["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in response.tool_calls
                    ]
                messages.append(assistant_message)
                if self.state is not None:
                    self.state.append_message(
                        request.session_id,
                        "assistant",
                        response.content or "",
                        {
                            "turn": turn_index + 1,
                            "tool_calls": [call.name for call in response.tool_calls],
                        },
                    )

                if not response.tool_calls:
                    strict_status = RuntimeStatus.FINAL
                    parsed_final = None
                    if self.profile.strict_output and response.content:
                        repaired_content = await self._repair_final_output(
                            response.content,
                            context_result.messages,
                            tool_schemas,
                            errors,
                            trace_events,
                            request.session_id,
                            turn_index + 1,
                        )
                        if repaired_content is not None:
                            response.content = repaired_content
                        else:
                            result = AgentRunResult(
                                status="blocked",
                                final_text=response.content or "",
                                messages=messages,
                                turns_used=turn_index + 1,
                                tool_results=all_tool_results,
                                usage=usage_totals,
                                errors=errors,
                                trace_events=trace_events,
                            )
                            self.hooks.emit(
                                EventType.AGENT_POST_RUN,
                                {"session_id": request.session_id, "status": result.status},
                            )
                            return result
                        parsed_final = self.strict_output_parser.parse(response.content)
                        strict_status = RuntimeStatus.from_strict_status(parsed_final.status)
                        if strict_status != RuntimeStatus.FINAL:
                            self._record_trace_event(
                                trace_events,
                                "finalization.result",
                                request.session_id,
                                turn=turn_index + 1,
                                status=str(strict_status.value),
                                attributes={"strict_status": parsed_final.status},
                            )
                            result = AgentRunResult(
                                status=str(strict_status.value),
                                final_text=response.content or "",
                                messages=messages,
                                turns_used=turn_index + 1,
                                tool_results=all_tool_results,
                                usage=usage_totals,
                                errors=errors,
                                trace_events=trace_events,
                            )
                            self.hooks.emit(
                                EventType.AGENT_POST_RUN,
                                {"session_id": request.session_id, "status": result.status},
                            )
                            return result
                    self._record_trace_event(
                        trace_events,
                        "finalization.check",
                        request.session_id,
                        turn=turn_index + 1,
                        status="started",
                        attributes={
                            "tool_results": len(all_tool_results),
                            "strict_output": parsed_final is not None,
                        },
                    )
                    finalization = self.finalization_guard.validate(
                        final_text=response.content or "",
                        artifacts=self.artifact_store.list_artifacts(request.session_id) if self.artifact_store else [],
                        evidence=self.evidence_ledger.list_evidence(request.session_id) if self.evidence_ledger else [],
                        tool_results=all_tool_results,
                        strict_output=parsed_final,
                    )
                    final_errors = errors + finalization.errors
                    self._record_trace_event(
                        trace_events,
                        "finalization.result",
                        request.session_id,
                        turn=turn_index + 1,
                        status=finalization.status,
                        attributes={
                            "verified": finalization.verified,
                            "error_count": len(finalization.errors),
                        },
                    )
                    result = AgentRunResult(
                        status=finalization.status,
                        final_text=response.content or "",
                        final_verified=finalization.verified,
                        messages=messages,
                        turns_used=turn_index + 1,
                        tool_results=all_tool_results,
                        usage=usage_totals,
                        errors=final_errors,
                        trace_events=trace_events,
                    )
                    self.hooks.emit(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
                    self._record_checkpoint(
                        request.session_id,
                        phase="agent.finalization",
                        status=result.status,
                        task_contract_hash=request.task_contract_hash,
                        prompt_stack_hash=request.prompt_stack_hash,
                        metadata={"turns_used": result.turns_used, "error_count": len(result.errors)},
                    )
                    return result

                for call in response.tool_calls:
                    self._record_trace_event(
                        trace_events,
                        "tool.request",
                        request.session_id,
                        turn=turn_index + 1,
                        status="started",
                        tool_name=call.name,
                        tool_call_id=call.id,
                        attributes={"arguments": call.arguments, "gen_ai.operation.name": "execute_tool"},
                    )
                    tool_result = self._maybe_block_exhausted_tool_retry(
                        call,
                        exhausted_retry_fingerprints,
                        exhausted_shape_fingerprints,
                    )
                    if tool_result is None:
                        tool_result = self.dispatcher.dispatch(
                            call,
                            ToolContext(
                                session_id=request.session_id,
                                workspace=self.workspace,
                                allowed_tools=request.allowed_tools,
                                allowed_tool_permissions=request.allowed_tool_permissions,
                                hooks=self.hooks,
                                state=self.state,
                            ),
                        )
                    self._apply_tool_failure_retry_budget(
                        call,
                        tool_result,
                        repair_failure_counts,
                        exhausted_retry_fingerprints,
                        exhausted_shape_fingerprints,
                    )
                    tool_result_event = self._record_trace_event(
                        trace_events,
                        "tool.result",
                        request.session_id,
                        turn=turn_index + 1,
                        status=tool_result.status,
                        tool_name=tool_result.tool_name,
                        tool_call_id=tool_result.tool_call_id,
                        attributes={
                            "failed": tool_result.failed,
                            "metadata": tool_result.metadata,
                            "error": tool_result.error,
                            "gen_ai.operation.name": "execute_tool",
                        },
                    )
                    self._record_schema_repair_hint_event(
                        trace_events,
                        request.session_id,
                        turn=turn_index + 1,
                        tool_result=tool_result,
                        parent_event_id=str(tool_result_event.get("event_id", "")),
                    )
                    all_tool_results.append(tool_result)
                    if self.state is not None:
                        self.state.record_tool_call(
                            request.session_id,
                            call.name,
                            call.arguments,
                            result=tool_result.content,
                            status=tool_result.status,
                            error=tool_result.error,
                            call_id=call.id or None,
                        )
                    if tool_result.failed:
                        errors.append(tool_result.error or tool_result.content)
                    if self.evidence_ledger is not None:
                        evidence_refs: list[str] = []
                        for extracted in self.evidence_extractor.extract(tool_result):
                            record = self.evidence_ledger.record_claim(
                                session_id=request.session_id,
                                claim=extracted.claim,
                                source_type=extracted.source_type,
                                source_ref=extracted.source_ref,
                                metadata=extracted.metadata,
                            )
                            evidence_refs.append(record.id)
                        if evidence_refs:
                            tool_result.metadata["evidence_refs"] = evidence_refs
                    tool_feedback = self._tool_feedback_content(tool_result)
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": tool_feedback,
                    }
                    messages.append(tool_message)
                    if self.state is not None:
                        self.state.append_message(
                            request.session_id,
                            "tool",
                            tool_feedback,
                            {"tool": call.name, "tool_call_id": call.id},
                        )

            result = AgentRunResult(
                status="max_turns",
                final_text="",
                messages=messages,
                turns_used=request.max_turns,
                tool_results=all_tool_results,
                usage=usage_totals,
                errors=errors + ["Maximum turns reached"],
                trace_events=trace_events,
            )
            self.hooks.emit(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
            return result
        except Exception as exc:
            self._record_trace_event(
                trace_events,
                "agent.error",
                request.session_id,
                status="error",
                attributes={"error": f"{type(exc).__name__}: {exc}"},
            )
            self.hooks.emit(EventType.AGENT_ERROR, {"session_id": request.session_id, "error": str(exc)})
            raise

    @staticmethod
    def _merge_usage(target: dict[str, int], usage: dict[str, Any]) -> None:
        for key, value in usage.items():
            if isinstance(value, int):
                target[key] = target.get(key, 0) + value

    @staticmethod
    def _record_trace_event(
        events: list[dict[str, Any]],
        event_type: str,
        session_id: str,
        *,
        turn: int | None = None,
        status: str = "",
        tool_name: str = "",
        tool_call_id: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        index = len(events)
        event = {
            "index": index,
            "event_id": f"{session_id}:{index:03d}:{event_type}",
            "event_type": event_type,
            "session_id": session_id,
            "status": status,
            "attributes": attributes or {},
        }
        if turn is not None:
            event["turn"] = turn
        if tool_name:
            event["tool_name"] = tool_name
        if tool_call_id:
            event["tool_call_id"] = tool_call_id
        events.append(event)
        return event

    def _record_checkpoint(
        self,
        session_id: str,
        *,
        phase: str,
        status: str,
        task_contract_hash: str = "",
        prompt_stack_hash: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.state is None or not hasattr(self.state, "record_checkpoint"):
            return
        self.state.record_checkpoint(
            session_id,
            phase=phase,
            status=status,
            task_contract_hash=task_contract_hash,
            prompt_stack_hash=prompt_stack_hash,
            metadata=metadata or {},
        )

    @staticmethod
    def _record_schema_repair_hint_event(
        events: list[dict[str, Any]],
        session_id: str,
        *,
        turn: int,
        tool_result: ToolResult,
        parent_event_id: str,
    ) -> None:
        metadata = tool_result.metadata
        hints = metadata.get("schema_repair_hints")
        hint_types = metadata.get("schema_repair_hint_types")
        hint_details = metadata.get("schema_repair_hint_details")
        if not isinstance(hints, list) or not hints:
            return
        if not isinstance(hint_types, list):
            hint_types = []
        if not isinstance(hint_details, list):
            hint_details = []
        event = AgentLoop._record_trace_event(
            events,
            "schema.repair_hint",
            session_id,
            turn=turn,
            status="emitted",
            tool_name=tool_result.tool_name,
            tool_call_id=tool_result.tool_call_id,
            attributes={
                "parent_event_id": parent_event_id,
                "schema_errors": metadata.get("schema_errors", []),
                "schema_repair_hints": hints,
                "schema_repair_hint_types": hint_types,
                "schema_repair_hint_details": hint_details,
                "hint_count": len(hints),
            },
        )
        event["summary"] = f"schema_repair_hint_types={','.join(str(hint_type) for hint_type in hint_types) or 'unknown'}"

    @staticmethod
    def _tool_feedback_content(tool_result: ToolResult) -> str:
        failure_type = tool_result.metadata.get("failure_type")
        if not failure_type:
            evidence_refs = tool_result.metadata.get("evidence_refs")
            if isinstance(evidence_refs, list) and evidence_refs:
                return json.dumps(
                    {
                        "result": AgentLoop._json_or_text(tool_result.content),
                        "evidence_refs": evidence_refs,
                        "evidence_instruction": (
                            "Use these evidence_refs in the final JSON when making claims supported by this tool result."
                        ),
                    },
                    ensure_ascii=False,
                )
            return tool_result.content
        feedback: dict[str, Any] = {
            "error_type": failure_type,
            "tool": tool_result.tool_name,
            "status": tool_result.status,
            "error": tool_result.error or tool_result.content,
            "recoverable": tool_result.metadata.get("recoverable", False),
            "retry_allowed": tool_result.metadata.get("retry_allowed", False),
            "repair_instruction": tool_result.metadata.get("repair_instruction", ""),
        }
        if "schema_errors" in tool_result.metadata:
            feedback["schema_errors"] = tool_result.metadata["schema_errors"]
            hints = tool_result.metadata.get("schema_repair_hints")
            hint_types = tool_result.metadata.get("schema_repair_hint_types")
            hint_details = tool_result.metadata.get("schema_repair_hint_details")
            if not isinstance(hints, list):
                schema_feedback = schema_repair_feedback(tool_result.metadata["schema_errors"])
                hints = schema_feedback["hints"]
                hint_types = schema_feedback["hint_types"]
                hint_details = schema_feedback["details"]
                tool_result.metadata["schema_repair_hints"] = hints
                tool_result.metadata["schema_repair_hint_types"] = hint_types
                tool_result.metadata["schema_repair_hint_details"] = hint_details
            feedback["schema_repair_hints"] = hints
            if isinstance(hint_types, list):
                feedback["schema_repair_hint_types"] = hint_types
            if isinstance(hint_details, list):
                feedback["schema_repair_hint_details"] = hint_details
        if "policy_decision" in tool_result.metadata:
            feedback["policy_decision"] = tool_result.metadata["policy_decision"]
        if "risk_level" in tool_result.metadata:
            feedback["risk_level"] = tool_result.metadata["risk_level"]
        if "exit_code" in tool_result.metadata:
            feedback["exit_code"] = tool_result.metadata["exit_code"]
        if "failure_shape_key" in tool_result.metadata:
            feedback["failure_shape_key"] = tool_result.metadata["failure_shape_key"]
        return json.dumps(feedback, ensure_ascii=False)

    @staticmethod
    def _json_or_text(content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content

    def _apply_tool_failure_retry_budget(
        self,
        call: ToolCall,
        tool_result: ToolResult,
        repair_failure_counts: dict[tuple[str, str], int],
        exhausted_retry_fingerprints: dict[tuple[str, str], str],
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str],
    ) -> None:
        failure_type = tool_result.metadata.get("failure_type")
        if not isinstance(failure_type, str) or not tool_result.metadata.get("recoverable", False):
            return
        key = (tool_result.tool_name, failure_type)
        repair_failure_counts[key] = repair_failure_counts.get(key, 0) + 1
        attempts = repair_failure_counts[key]
        tool_result.metadata["repair_attempt_number"] = attempts
        tool_result.metadata["max_tool_repair_retries"] = self.profile.max_tool_repair_retries
        lineage_key = self._tool_call_lineage_key(call)
        tool_result.metadata["failure_lineage_key"] = lineage_key[1]
        shape_key = self._tool_failure_shape_key(call, tool_result)
        if shape_key is not None:
            tool_result.metadata["failure_shape_key"] = shape_key[2]
        if attempts > self.profile.max_tool_repair_retries:
            tool_result.metadata["retry_allowed"] = False
            tool_result.metadata["retry_budget_exhausted"] = True
            exhausted_retry_fingerprints[lineage_key] = failure_type
            if shape_key is not None:
                exhausted_shape_fingerprints[shape_key] = failure_type
            tool_result.metadata["repair_instruction"] = (
                "Retry budget exhausted for this tool and failure type. "
                "Do not repeat this tool call pattern; choose a different allowed approach or return blocked."
            )

    def _maybe_block_exhausted_tool_retry(
        self,
        call: ToolCall,
        exhausted_retry_fingerprints: dict[tuple[str, str], str],
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str],
    ) -> ToolResult | None:
        lineage_key = self._tool_call_lineage_key(call)
        original_failure_type = exhausted_retry_fingerprints.get(lineage_key)
        shape_key = self._predict_tool_failure_shape_key(call)
        if original_failure_type is None and shape_key is not None:
            original_failure_type = exhausted_shape_fingerprints.get(shape_key)
        if original_failure_type is None:
            return None
        error = (
            "Retry budget exhausted for this repeated tool call pattern: "
            f"{call.name} after {original_failure_type}"
        )
        return ToolResult(
            call.name,
            json.dumps({"error": error}, ensure_ascii=False),
            status="blocked",
            tool_call_id=call.id,
            error=error,
            metadata=tool_failure_metadata(
                ToolFailureType.RETRY_BUDGET_EXHAUSTED,
                retry_allowed=False,
                extra={
                    "original_failure_type": original_failure_type,
                    "pre_dispatch_block": True,
                    "retry_budget_exhausted": True,
                    "failure_lineage_key": lineage_key[1],
                    "failure_shape_key": shape_key[2] if shape_key is not None else None,
                },
            ),
        )

    @staticmethod
    def _tool_call_lineage_key(call: ToolCall) -> tuple[str, str]:
        return (call.name, json.dumps(call.arguments, ensure_ascii=False, sort_keys=True))

    def _tool_failure_shape_key(self, call: ToolCall, tool_result: ToolResult) -> tuple[str, str, str] | None:
        failure_type = tool_result.metadata.get("failure_type")
        if failure_type == ToolFailureType.SCHEMA_VALIDATION_FAILED.value:
            schema_errors = tool_result.metadata.get("schema_errors", [])
            if isinstance(schema_errors, list) and schema_errors:
                return (call.name, failure_type, "|".join(str(error) for error in schema_errors))
        if failure_type == ToolFailureType.COMMAND_FAILED.value:
            command_shape = self._command_semantic_shape(call)
            if command_shape:
                return (call.name, failure_type, command_shape)
        if failure_type == ToolFailureType.RUNTIME_ERROR.value:
            exception_type = str(tool_result.metadata.get("exception_type", "unknown"))
            error = str(tool_result.error or "")
            return (call.name, failure_type, f"{exception_type}:{self._normalize_error_text(error)}")
        return None

    def _predict_tool_failure_shape_key(self, call: ToolCall) -> tuple[str, str, str] | None:
        command_shape = self._command_semantic_shape(call)
        if command_shape is not None:
            command_key = (call.name, ToolFailureType.COMMAND_FAILED.value, command_shape)
            return command_key

        spec = self.registry.get(call.name)
        if spec is None:
            return None
        schema_result = self.dispatcher.schema_validator.validate(spec.parameters, call.arguments)
        if schema_result.passed:
            return None
        return (
            call.name,
            ToolFailureType.SCHEMA_VALIDATION_FAILED.value,
            "|".join(schema_result.errors),
        )

    @staticmethod
    def _command_semantic_shape(call: ToolCall) -> str | None:
        raw_command = call.arguments.get("command")
        if raw_command is None:
            return None
        if isinstance(raw_command, list):
            parts = [str(item) for item in raw_command]
        else:
            try:
                parts = shlex.split(str(raw_command))
            except ValueError:
                parts = str(raw_command).split()
        normalized = [AgentLoop._normalize_command_part(part) for part in parts if str(part).strip()]
        normalized = [part for part in normalized if part]
        if not normalized:
            return None
        if len(normalized) == 1:
            return normalized[0]
        return " ".join(normalized[:2])

    @staticmethod
    def _normalize_command_part(part: str) -> str:
        lowered = part.lower().strip()
        if lowered.startswith("-"):
            return ""
        if any(ch.isdigit() for ch in lowered):
            return "<value>"
        if any(sep in lowered for sep in ("\\", "/", ".")):
            return "<path>"
        return lowered

    @staticmethod
    def _normalize_error_text(error: str) -> str:
        normalized_parts = []
        for part in error.lower().split():
            if any(ch.isdigit() for ch in part):
                normalized_parts.append("<value>")
            elif any(sep in part for sep in ("\\", "/", ".")):
                normalized_parts.append("<path>")
            else:
                normalized_parts.append(part)
        return " ".join(normalized_parts)

    async def _parse_tool_calls_with_repair(
        self,
        raw: Any,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        errors: list[str],
        trace_events: list[dict[str, Any]],
        session_id: str,
        turn: int,
    ):
        for attempt in range(self.profile.parser_repair_retries + 1):
            try:
                calls = self.tool_call_parser.parse(raw)
                if attempt > 0:
                    self._record_trace_event(
                        trace_events,
                        "parser.repair.result",
                        session_id,
                        turn=turn,
                        status="ok",
                        attributes={"attempt": attempt, "tool_call_count": len(calls)},
                    )
                return calls
            except ParserError as exc:
                errors.append(f"ParserError: {exc}")
                if attempt >= self.profile.parser_repair_retries:
                    self._record_trace_event(
                        trace_events,
                        "parser.repair.result",
                        session_id,
                        turn=turn,
                        status="failed",
                        attributes={"attempt": attempt, "error": str(exc)},
                    )
                    return []
                self._record_trace_event(
                    trace_events,
                    "parser.repair.request",
                    session_id,
                    turn=turn,
                    status="started",
                    attributes={"attempt": attempt + 1, "error": str(exc)},
                )
                repair_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            "Your previous tool call could not be parsed. Return the corrected tool call only, "
                            f"using one of the available tool schemas. Parser error: {exc}"
                        ),
                    }
                ]
                repaired = await self.provider.complete(repair_messages, tools=tool_schemas)
                raw = repaired.raw if isinstance(repaired.raw, str) else repaired.content
        return []

    async def _repair_final_output(
        self,
        content: str,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        errors: list[str],
        trace_events: list[dict[str, Any]],
        session_id: str,
        turn: int,
    ) -> str | None:
        try:
            self.strict_output_parser.parse(content)
            return content
        except Exception as exc:
            errors.append(f"StrictOutputError: {exc}")
            self._record_trace_event(
                trace_events,
                "finalization.repair.request",
                session_id,
                turn=turn,
                status="started",
                attributes={"error": str(exc)},
            )
            repaired = await self.provider.complete(
                messages + [self.strict_output_parser.repair_prompt(exc, content)],
                tools=[],
            )
            try:
                self.strict_output_parser.parse(repaired.content)
                self._record_trace_event(
                    trace_events,
                    "finalization.repair.result",
                    session_id,
                    turn=turn,
                    status="ok",
                    attributes={"content_chars": len(repaired.content or "")},
                )
                return repaired.content
            except Exception as repair_exc:
                errors.append(f"StrictOutputRepairError: {repair_exc}")
                self._record_trace_event(
                    trace_events,
                    "finalization.repair.result",
                    session_id,
                    turn=turn,
                    status="failed",
                    attributes={"error": str(repair_exc)},
                )
                return None
