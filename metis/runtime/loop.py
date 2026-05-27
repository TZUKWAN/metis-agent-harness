"""Minimal multi-turn agent loop."""

from __future__ import annotations

import asyncio
import json
import shlex
import time
from typing import Any, Protocol, runtime_checkable

from metis.config import MAX_SAME_TOOL_PER_SESSION, TEMP_BASE, TEMP_LOOP_BOOST, TEMP_MAX, TEMP_PER_TURN, TEMP_REPAIR_BOOST
from metis.context.engine import ContextEngine
from metis.evidence.extractor import ToolEvidenceExtractor
from metis.evidence.resolver import EvidenceResolver
from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.logging import get_logger
from metis.providers.base import BaseProvider
from metis.runtime.budgets import BudgetConfig
from metis.runtime.errors import ParserError
from metis.runtime.finalization import FinalizationGuard
from metis.runtime.profiles import ModelProfile, get_model_profile
from metis.runtime.response import AgentRunRequest, AgentRunResult, NormalizedResponse, ToolCall, ToolResult
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

logger = get_logger("loop")


@runtime_checkable
class StateStore(Protocol):
    def create_session(self, session_id: str, **kwargs: Any) -> str: ...
    def append_message(self, session_id: str, role: str, content: str, **kwargs: Any) -> int: ...
    def record_tool_call(self, session_id: str, tool_name: str, args: dict[str, Any], **kwargs: Any) -> str: ...
    def record_checkpoint(self, session_id: str, *, phase: str, status: str, **kwargs: Any) -> str: ...
    def record_token_usage(self, session_id: str, **kwargs: Any) -> None: ...


def _is_shutdown_requested() -> bool:
    try:
        from metis.runtime.shutdown import is_shutdown_requested
        return is_shutdown_requested()
    except ImportError:
        return False


class AgentLoop:
    """Execute model calls and tool calls until a final response or max_turns."""

    _SESSION_TOOL_COUNTS: dict[str, dict[str, int]] = {}
    _MAX_SAME_TOOL_PER_SESSION = MAX_SAME_TOOL_PER_SESSION
    _SESSION_TOOL_FAILURES: dict[str, dict[str, list[float]]] = {}
    _CIRCUIT_BREAKER_THRESHOLD = 3
    _CIRCUIT_BREAKER_WINDOW = 300
    _CIRCUIT_BREAKER_COOLDOWN = 60
    _MAX_TRACKED_SESSIONS = 1000
    _SESSION_ACTIVITY_TTL = 3600
    _SESSION_LAST_ACTIVITY: dict[str, float] = {}

    def __init_instance_state(self) -> None:
        self._session_tool_counts: dict[str, dict[str, int]] = {}
        self._session_tool_failures: dict[str, dict[str, list[float]]] = {}
        self._session_last_activity: dict[str, float] = {}

    def __init__(
        self,
        *,
        provider: BaseProvider,
        registry: ToolRegistry,
        dispatcher: ToolDispatcher | None = None,
        hooks: HookBus | None = None,
        workspace: str = ".",
        state: StateStore | None = None,
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
        try:
            caps = provider.capabilities()
            detected_tokens = caps.max_context_tokens
            detected_max_output = caps.max_output_tokens
        except Exception:
            detected_tokens = 0
            detected_max_output = 0
        self.context_engine = context_engine or ContextEngine(
            budget=self.budget,
            override_max_context_tokens=detected_tokens if detected_tokens > 0 else None,
        )
        self.per_turn_timeout = self._compute_per_turn_timeout(detected_max_output)
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
        self.__init_instance_state()

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        logger.info("Agent run started session=%s max_turns=%d profile=%s", request.session_id, request.max_turns, self.profile.name)
        messages = list(request.messages)
        all_tool_results: list[ToolResult] = []
        usage_totals: dict[str, int] = {}
        errors: list[str] = []
        trace_events: list[dict[str, Any]] = []
        repair_failure_counts: dict[tuple[str, str], int] = {}
        exhausted_retry_fingerprints: dict[tuple[str, str], str] = {}
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str] = {}
        total_tool_calls = 0
        tool_result_cache: dict[str, ToolResult] = {}
        agent_memory: dict[str, str] = {}
        turn_signatures: list[str] = []
        self._session_tool_counts.pop(request.session_id, None)
        self._session_tool_failures.pop(request.session_id, None)
        self._session_last_activity[request.session_id] = time.monotonic()
        AgentLoop._prune_session_state()

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
                "request_id": request.request_id,
            },
        )
        await self.hooks.emit_async(EventType.AGENT_PRE_RUN, {"session_id": request.session_id})
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
                turn_start = time.monotonic()
                await self.hooks.emit_async(
                    EventType.BEHAVIOR_CHECKPOINT,
                    {
                        "session_id": request.session_id,
                        "turn": turn_index + 1,
                        "phase": "turn.start",
                        "metadata": {"turns_used": turn_index, "max_turns": request.max_turns},
                    },
                )
                if _is_shutdown_requested():
                    logger.warning("Shutdown requested at turn %d, saving checkpoint", turn_index + 1)
                    if self.state is not None:
                        self._record_checkpoint(
                            request.session_id, phase="agent.shutdown", status="interrupted",
                            task_contract_hash=request.task_contract_hash,
                            prompt_stack_hash=request.prompt_stack_hash,
                            metadata={"turns_used": turn_index, "shutdown": True},
                        )
                    result = AgentRunResult(
                        status="interrupted",
                        final_text="Shutdown requested by user",
                        messages=messages,
                        turns_used=turn_index,
                        tool_results=all_tool_results,
                        usage=usage_totals,
                        errors=errors,
                        trace_events=trace_events,
                    )
                    return result
                tool_schemas = self.tool_router.schemas(
                    ToolRouteRequest(stage="execute", allowed_tools=request.allowed_tools, profile=self.profile)
                )

                await self.hooks.emit_async(
                    EventType.MODEL_PRE_CALL,
                    {"session_id": request.session_id, "turn": turn_index + 1, "tool_count": len(tool_schemas)},
                )
                context_result = self.context_engine.build(messages, tool_schemas=tool_schemas)
                provider_messages = self._ensure_reasoning_content(
                    context_result.messages, self.provider.capabilities().thinking
                )
                est_tokens = context_result.final_chars // max(1, self.context_engine.chars_per_token)
                temperature = self._compute_temperature(
                    turn_index, repair_failure_counts, turn_signatures
                )
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
                        "model": getattr(self.provider, "model", ""),
                        "estimated_tokens": est_tokens,
                        "max_chars_budget": context_result.max_chars,
                        "compression_ratio": round(context_result.original_chars / max(1, context_result.final_chars), 2) if context_result.compressed else 1.0,
                        "per_turn_timeout": self.per_turn_timeout,
                        "temperature": temperature,
                        "gen_ai.operation.name": "chat",
                    },
                )
                if context_result.compressed:
                    await self.hooks.emit_async(
                        "context.compressed",
                        {
                            "session_id": request.session_id,
                            "turn": turn_index + 1,
                            "original_chars": context_result.original_chars,
                            "final_chars": context_result.final_chars,
                            "max_chars": context_result.max_chars,
                        },
                    )
                try:
                    response = await asyncio.wait_for(
                        self._call_provider(
                            provider_messages, tools=tool_schemas, temperature=temperature,
                            session_id=request.session_id, turn=turn_index + 1,
                        ),
                        timeout=self.per_turn_timeout,
                    )
                except Exception as exc:
                    error_str = str(exc).lower()
                    if "context" in error_str or "too long" in error_str or "length" in error_str:
                        logger.warning("Turn %d context length error, aggressive recompression", turn_index + 1)
                        original_len = len(provider_messages)
                        # Aggressive fallback: recompress with tighter budget instead of naive truncation
                        aggressive_result = self.context_engine.build(
                            messages,
                            tool_schemas=tool_schemas,
                        )
                        # Force a tighter threshold by temporarily lowering budget
                        from dataclasses import replace
                        old_budget = self.context_engine.budget
                        tighter_budget = replace(old_budget, context_threshold=old_budget.context_threshold * 0.7)
                        self.context_engine.budget = tighter_budget
                        try:
                            aggressive_result = self.context_engine.build(messages, tool_schemas=tool_schemas)
                        finally:
                            self.context_engine.budget = old_budget

                        recompressed = self._ensure_reasoning_content(
                            aggressive_result.messages, self.provider.capabilities().thinking
                        )
                        if len(recompressed) < original_len:
                            self._record_trace_event(
                                trace_events, "context.recompressed", request.session_id,
                                turn=turn_index + 1, status="recompressed",
                                attributes={
                                    "original_messages": original_len,
                                    "recompressed_messages": len(recompressed),
                                    "original_tokens": aggressive_result.original_tokens,
                                    "final_tokens": aggressive_result.final_tokens,
                                    "tool_schema_tokens": aggressive_result.tool_schema_tokens,
                                },
                            )
                            try:
                                response = await asyncio.wait_for(
                                    self._call_provider(
                                        recompressed, tools=tool_schemas, temperature=temperature,
                                        session_id=request.session_id, turn=turn_index + 1,
                                    ),
                                    timeout=self.per_turn_timeout,
                                )
                            except Exception as retry_exc:
                                retry_error = str(retry_exc).lower()
                                if "context" in retry_error or "too long" in retry_error or "length" in retry_error:
                                    # Third-line defense: force-truncate and retry one more time
                                    logger.warning("Turn %d still over context after recompression, force-truncating", turn_index + 1)
                                    truncated = self._truncate_for_context(recompressed)
                                    if len(truncated) < len(recompressed):
                                        self._record_trace_event(
                                            trace_events, "context.force_truncated", request.session_id,
                                            turn=turn_index + 1, status="force_truncated",
                                            attributes={
                                                "original_messages": original_len,
                                                "truncated_messages": len(truncated),
                                            },
                                        )
                                        try:
                                            response = await asyncio.wait_for(
                                                self._call_provider(
                                                    truncated, tools=tool_schemas, temperature=temperature,
                                                    session_id=request.session_id, turn=turn_index + 1,
                                                ),
                                                timeout=self.per_turn_timeout,
                                            )
                                        except Exception as trunc_exc:
                                            errors.append(f"Turn {turn_index + 1} failed after force-truncation: {trunc_exc}")
                                            continue
                                    else:
                                        errors.append(f"Turn {turn_index + 1} failed: {retry_exc}")
                                        continue
                                else:
                                    errors.append(f"Turn {turn_index + 1} failed after recompression: {retry_exc}")
                                    continue
                        else:
                            errors.append(f"Turn {turn_index + 1} failed: {exc}")
                            continue
                    elif isinstance(exc, asyncio.TimeoutError):
                        logger.warning("Turn %d timed out after %ds", turn_index + 1, self.per_turn_timeout)
                        errors.append(f"Turn {turn_index + 1} timed out after {self.per_turn_timeout}s")
                        continue
                    else:
                        raise
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
                await self.hooks.emit_async(
                    EventType.MODEL_POST_CALL,
                    {"session_id": request.session_id, "turn": turn_index + 1, "usage": response.usage},
                )
                self._merge_usage(usage_totals, response.usage)
                turn_duration_ms = int((time.monotonic() - turn_start) * 1000)
                self._record_trace_event(
                    trace_events,
                    "turn.timing",
                    request.session_id,
                    turn=turn_index + 1,
                    status="ok",
                    attributes={"turn_duration_ms": turn_duration_ms},
                )
                await self.hooks.emit_async(
                    "turn.complete",
                    {
                        "session_id": request.session_id,
                        "turn": turn_index + 1,
                        "turn_duration_ms": turn_duration_ms,
                        "tool_call_count": len(response.tool_calls),
                    },
                )
                await self.hooks.emit_async(
                    EventType.BEHAVIOR_CHECKPOINT,
                    {
                        "session_id": request.session_id,
                        "turn": turn_index + 1,
                        "phase": "turn.complete",
                        "metadata": {"tool_call_count": len(response.tool_calls), "turn_duration_ms": turn_duration_ms},
                    },
                )
                if response.usage:
                    await self.hooks.emit_async(
                        "model.token_usage",
                        {
                            "session_id": request.session_id,
                            "turn": turn_index + 1,
                            "turn_usage": response.usage,
                            "cumulative_usage": dict(usage_totals),
                        },
                    )

                if response.tool_calls and self.profile.one_tool_call_per_turn and len(response.tool_calls) > 1:
                    logger.debug("Truncating %d tool calls to 1 (one_tool_call_per_turn)", len(response.tool_calls))
                    self._record_trace_event(
                        trace_events, "tool.truncate", request.session_id,
                        turn=turn_index + 1, status="truncated",
                        attributes={"original_count": len(response.tool_calls), "kept": 1},
                    )
                    response.tool_calls = [response.tool_calls[0]]

                turn_signatures.append(AgentLoop._turn_signature(response))
                if AgentLoop._detect_response_loop(turn_signatures):
                    loop_reason = f"Response loop detected: same pattern repeated for 3 consecutive turns"
                    logger.warning(loop_reason)
                    self._record_trace_event(
                        trace_events, "agent.loop_detected", request.session_id,
                        turn=turn_index + 1, status="blocked",
                        attributes={"pattern": turn_signatures[-1]},
                    )
                    errors.append(loop_reason)
                    result = AgentRunResult(
                        status=RuntimeStatus.BLOCKED.value,
                        final_text="",
                        messages=messages,
                        turns_used=turn_index + 1,
                        tool_results=all_tool_results,
                        usage=usage_totals,
                        errors=errors,
                        trace_events=trace_events,
                    )
                    await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
                    return result

                if response.tool_calls and len(response.tool_calls) > self.profile.max_tool_calls_per_turn:
                    reason = (
                        f"Tool call limit exceeded: got {len(response.tool_calls)}, "
                        f"max={self.profile.max_tool_calls_per_turn}"
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
                    await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
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
                reasoning = getattr(response, "reasoning", None)
                if reasoning:
                    assistant_message["reasoning_content"] = reasoning
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
                    # Thinking-enabled APIs require reasoning_content on tool call messages
                    if "reasoning_content" not in assistant_message:
                        assistant_message["reasoning_content"] = reasoning or ""
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
                    result = await self._finalize_turn(
                        response=response,
                        context_messages=context_result.messages,
                        tool_schemas=tool_schemas,
                        messages=messages,
                        all_tool_results=all_tool_results,
                        usage_totals=usage_totals,
                        errors=errors,
                        trace_events=trace_events,
                        session_id=request.session_id,
                        turn_index=turn_index,
                        task_contract_hash=request.task_contract_hash,
                        prompt_stack_hash=request.prompt_stack_hash,
                    )
                    if result is not None:
                        return result

                if self.profile.concurrent_tool_dispatch and len(response.tool_calls) > 1:
                    total_tool_calls = await self._dispatch_tool_calls_batch(
                        calls=response.tool_calls,
                        session_id=request.session_id,
                        turn_index=turn_index,
                        messages=messages,
                        all_tool_results=all_tool_results,
                        errors=errors,
                        trace_events=trace_events,
                        repair_failure_counts=repair_failure_counts,
                        exhausted_retry_fingerprints=exhausted_retry_fingerprints,
                        exhausted_shape_fingerprints=exhausted_shape_fingerprints,
                        allowed_tools=request.allowed_tools,
                        allowed_tool_permissions=request.allowed_tool_permissions,
                        tool_result_cache=tool_result_cache,
                        total_tool_calls=total_tool_calls,
                    )
                    if total_tool_calls > self.profile.max_session_tool_calls:
                        result = AgentRunResult(
                            status=RuntimeStatus.BLOCKED.value,
                            final_text="",
                            messages=messages,
                            turns_used=turn_index + 1,
                            tool_results=all_tool_results,
                            usage=usage_totals,
                            errors=errors,
                            trace_events=trace_events,
                        )
                        await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
                        return result
                else:
                    for call in response.tool_calls:
                        total_tool_calls += 1
                        if total_tool_calls > self.profile.max_session_tool_calls:
                            reason = f"Session tool call limit exceeded: {total_tool_calls} calls, max={self.profile.max_session_tool_calls}"
                            logger.warning(reason)
                            errors.append(reason)
                            self._record_trace_event(
                                trace_events, "tool.session_limit", request.session_id,
                                turn=turn_index + 1, status="blocked",
                                attributes={"total_tool_calls": total_tool_calls, "limit": self.profile.max_session_tool_calls},
                            )
                            result = AgentRunResult(
                                status=RuntimeStatus.BLOCKED.value,
                                final_text="",
                                messages=messages,
                                turns_used=turn_index + 1,
                                tool_results=all_tool_results,
                                usage=usage_totals,
                                errors=errors,
                                trace_events=trace_events,
                            )
                            await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
                            return result
                        await self._dispatch_tool_call(
                            call=call,
                            session_id=request.session_id,
                            turn_index=turn_index,
                            messages=messages,
                            all_tool_results=all_tool_results,
                            errors=errors,
                            trace_events=trace_events,
                            repair_failure_counts=repair_failure_counts,
                            exhausted_retry_fingerprints=exhausted_retry_fingerprints,
                            exhausted_shape_fingerprints=exhausted_shape_fingerprints,
                            allowed_tools=request.allowed_tools,
                            allowed_tool_permissions=request.allowed_tool_permissions,
                            tool_result_cache=tool_result_cache,
                        )

            result = AgentRunResult(
                status="max_turns",
                final_text=f"[Agent reached the maximum turn limit ({request.max_turns}). The task may be incomplete. Try increasing --max-turns or breaking the task into smaller steps.]",
                messages=messages,
                turns_used=request.max_turns,
                tool_results=all_tool_results,
                usage=usage_totals,
                errors=errors + [f"Maximum turns reached ({request.max_turns})"],
                trace_events=trace_events,
            )
            await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": request.session_id, "status": result.status})
            return result
        except Exception as exc:
            from metis.recovery.classifier import ErrorClassifier
            error_category = ErrorClassifier().classify(exc)
            self._record_trace_event(
                trace_events,
                "agent.error",
                request.session_id,
                status="error",
                attributes={"error": f"{type(exc).__name__}: {exc}", "error_category": error_category},
            )
            await self.hooks.emit_async(EventType.AGENT_ERROR, {"session_id": request.session_id, "error": str(exc), "category": error_category})
            raise
        finally:
            self._session_tool_counts.pop(request.session_id, None)
            self._session_tool_failures.pop(request.session_id, None)
            self._session_last_activity.pop(request.session_id, None)
            AgentLoop._cleanup_session_state(request.session_id)

    async def _call_provider(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        session_id: str,
        turn: int,
    ) -> NormalizedResponse:
        """Call provider with streaming if supported, otherwise use complete()."""
        if not self.provider.capabilities().streaming:
            return await self.provider.complete(
                messages, tools=tools, temperature=temperature
            )

        accumulated_content = ""
        accumulated_reasoning: str | None = None
        accumulated_tool_calls: list[Any] = []
        usage: dict[str, Any] = {}
        finish_reason = ""

        async for chunk in self.provider.complete_stream(
            messages, tools=tools, temperature=temperature
        ):
            if chunk.content:
                if chunk.is_finished:
                    accumulated_content = chunk.content
                else:
                    accumulated_content += chunk.content
            if chunk.reasoning:
                if accumulated_reasoning is None:
                    accumulated_reasoning = ""
                accumulated_reasoning += chunk.reasoning
            if chunk.tool_calls:
                accumulated_tool_calls = chunk.tool_calls
            if chunk.usage:
                usage = chunk.usage
            if chunk.is_finished and chunk.content:
                finish_reason = "stop"

            await self.hooks.emit_async(
                EventType.MODEL_STREAM_CHUNK,
                {
                    "session_id": session_id,
                    "turn": turn,
                    "content": chunk.content,
                    "reasoning": chunk.reasoning,
                    "is_finished": chunk.is_finished,
                },
            )

        return NormalizedResponse(
            content=accumulated_content,
            reasoning=accumulated_reasoning,
            tool_calls=accumulated_tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
            raw={"streamed": True},
        )

    @staticmethod
    def _ensure_reasoning_content(
        messages: list[dict[str, Any]], thinking_enabled: bool = False
    ) -> list[dict[str, Any]]:
        """Add empty reasoning_content to assistant tool call messages for thinking-enabled APIs."""
        if not thinking_enabled:
            return messages
        result: list[dict[str, Any]] = []
        for message in messages:
            cloned = dict(message)
            if cloned.get("role") == "assistant" and "tool_calls" in cloned:
                if "reasoning_content" not in cloned:
                    cloned["reasoning_content"] = ""
            result.append(cloned)
        return result

    @staticmethod
    def _cleanup_session_state(session_id: str) -> None:
        """Remove session-specific state to prevent memory leaks."""
        AgentLoop._SESSION_TOOL_COUNTS.pop(session_id, None)
        AgentLoop._SESSION_TOOL_FAILURES.pop(session_id, None)
        AgentLoop._SESSION_LAST_ACTIVITY.pop(session_id, None)

    @staticmethod
    def _prune_session_state() -> None:
        """Evict stale or excess session entries from class-level caches."""
        now = time.monotonic()
        stale_threshold = now - AgentLoop._SESSION_ACTIVITY_TTL
        stale_sessions = [
            sid for sid, last_active in AgentLoop._SESSION_LAST_ACTIVITY.items()
            if last_active < stale_threshold
        ]
        for sid in stale_sessions:
            AgentLoop._cleanup_session_state(sid)

        total_sessions = len(AgentLoop._SESSION_LAST_ACTIVITY)
        if total_sessions > AgentLoop._MAX_TRACKED_SESSIONS:
            sorted_sessions = sorted(
                AgentLoop._SESSION_LAST_ACTIVITY.items(), key=lambda x: x[1]
            )
            to_evict = sorted_sessions[: total_sessions - AgentLoop._MAX_TRACKED_SESSIONS]
            for sid, _ in to_evict:
                AgentLoop._cleanup_session_state(sid)

    @staticmethod
    def _compute_temperature(
        turn_index: int,
        repair_failure_counts: dict[tuple[str, str], int],
        turn_signatures: list[str],
    ) -> float:
        """Adjust temperature based on turn state to encourage response diversity."""
        turn_boost = min(turn_index * TEMP_PER_TURN, 0.35)
        repair_boost = TEMP_REPAIR_BOOST if any(c > 0 for c in repair_failure_counts.values()) else 0.0
        loop_boost = 0.0
        if len(turn_signatures) >= 2:
            if turn_signatures[-1] == turn_signatures[-2]:
                loop_boost = TEMP_LOOP_BOOST
        temp = TEMP_BASE + turn_boost + repair_boost + loop_boost
        return round(max(0.0, min(TEMP_MAX, temp)), 2)

    @staticmethod
    def _compute_per_turn_timeout(max_output_tokens: int) -> int:
        """Scale timeout based on model's max output tokens.

        Base 90s + 25s per 1K output tokens, clamped to [120, 600].
        """
        if max_output_tokens <= 0:
            from metis.config import PER_TURN_TIMEOUT
            return PER_TURN_TIMEOUT
        calculated = 90 + (max_output_tokens // 1000) * 25
        return max(120, min(600, calculated))

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
            content = tool_result.content
            from metis.tools.summarizer import summarize_tool_result
            summarized = summarize_tool_result(content, tool_result.tool_name)
            if summarized != content:
                content = summarized
            if isinstance(evidence_refs, list) and evidence_refs:
                return json.dumps(
                    {
                        "result": AgentLoop._json_or_text(content),
                        "evidence_refs": evidence_refs,
                        "evidence_instruction": (
                            "Use these evidence_refs in the final JSON when making claims supported by this tool result."
                        ),
                    },
                    ensure_ascii=False,
                )
            return content
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
    def _compact_feedback(content: str, max_chars: int = 4000) -> str:
        if len(content) <= max_chars:
            return content
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for key in ("error", "stderr"):
                    if key in data and isinstance(data[key], str) and len(data[key]) > 500:
                        data[key] = data[key][:500] + "... [truncated]"
                for key in ("stdout", "result"):
                    if key in data and isinstance(data[key], str) and len(data[key]) > 500:
                        data[key] = data[key][:500] + "... [truncated]"
                compacted = json.dumps(data, ensure_ascii=False)
                if len(compacted) <= max_chars:
                    return compacted
            return content[:max_chars] + "\n... [truncated]"
        except (json.JSONDecodeError, ValueError):
            return content[:max_chars] + "\n... [truncated]"

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
    def _truncate_for_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove oldest non-system messages to reduce context length."""
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = max(4, len(non_system) // 2)
        kept = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        return system_messages + kept

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

    async def _finalize_turn(
        self,
        *,
        response: NormalizedResponse,
        context_messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        all_tool_results: list[ToolResult],
        usage_totals: dict[str, int],
        errors: list[str],
        trace_events: list[dict[str, Any]],
        session_id: str,
        turn_index: int,
        task_contract_hash: str = "",
        prompt_stack_hash: str = "",
    ) -> AgentRunResult | None:
        """Handle the no-tool-call case: strict output parsing and finalization."""
        parsed_final = None
        if self.profile.strict_output and response.content:
            if self.profile.strict_output_soft:
                parsed_final = self.strict_output_parser.parse_soft(response.content)
                strict_status = RuntimeStatus.from_strict_status(parsed_final.status)
                if strict_status != RuntimeStatus.FINAL:
                    self._record_trace_event(
                        trace_events, "finalization.result", session_id,
                        turn=turn_index + 1, status=str(strict_status.value),
                        attributes={"strict_status": parsed_final.status},
                    )
                    result = AgentRunResult(
                        status=str(strict_status.value), final_text=response.content or "",
                        messages=messages, turns_used=turn_index + 1,
                        tool_results=all_tool_results, usage=usage_totals,
                        errors=errors, trace_events=trace_events,
                    )
                    await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": session_id, "status": result.status})
                    return result
            else:
                repaired_content = await self._repair_final_output(
                    response.content, context_messages, tool_schemas,
                    errors, trace_events, session_id, turn_index + 1,
                )
                if repaired_content is not None:
                    response.content = repaired_content
                else:
                    result = AgentRunResult(
                        status="blocked", final_text=response.content or "",
                        messages=messages, turns_used=turn_index + 1,
                        tool_results=all_tool_results, usage=usage_totals,
                        errors=errors, trace_events=trace_events,
                    )
                    await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": session_id, "status": result.status})
                    return result
                parsed_final = self.strict_output_parser.parse(response.content)
                strict_status = RuntimeStatus.from_strict_status(parsed_final.status)
                if strict_status != RuntimeStatus.FINAL:
                    self._record_trace_event(
                        trace_events, "finalization.result", session_id,
                        turn=turn_index + 1, status=str(strict_status.value),
                        attributes={"strict_status": parsed_final.status},
                    )
                    result = AgentRunResult(
                        status=str(strict_status.value), final_text=response.content or "",
                        messages=messages, turns_used=turn_index + 1,
                        tool_results=all_tool_results, usage=usage_totals,
                        errors=errors, trace_events=trace_events,
                    )
                    await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": session_id, "status": result.status})
                    return result
        self._record_trace_event(
            trace_events, "finalization.check", session_id,
            turn=turn_index + 1, status="started",
            attributes={"tool_results": len(all_tool_results), "strict_output": parsed_final is not None},
        )
        finalization = self.finalization_guard.validate(
            final_text=response.content or "",
            artifacts=self.artifact_store.list_artifacts(session_id) if self.artifact_store else [],
            evidence=self.evidence_ledger.list_evidence(session_id) if self.evidence_ledger else [],
            tool_results=all_tool_results,
            strict_output=parsed_final,
        )
        # Evaluate behavior-rules gates if enabled
        behavior_gate_errors = self._run_behavior_gates(
            session_id=session_id,
            final_text=response.content or "",
            tool_results=all_tool_results,
            artifacts=self.artifact_store.list_artifacts(session_id) if self.artifact_store else [],
            evidence=self.evidence_ledger.list_evidence(session_id) if self.evidence_ledger else [],
        )
        final_errors = errors + finalization.errors + behavior_gate_errors
        self._record_trace_event(
            trace_events, "finalization.result", session_id,
            turn=turn_index + 1, status=finalization.status,
            attributes={"verified": finalization.verified, "error_count": len(finalization.errors), "behavior_gate_errors": len(behavior_gate_errors)},
        )
        result = AgentRunResult(
            status=finalization.status, final_text=response.content or "",
            final_verified=finalization.verified, messages=messages,
            turns_used=turn_index + 1, tool_results=all_tool_results,
            usage=usage_totals, errors=final_errors, trace_events=trace_events,
        )
        await self.hooks.emit_async(EventType.AGENT_POST_RUN, {"session_id": session_id, "status": result.status})
        self._record_checkpoint(
            session_id, phase="agent.finalization", status=result.status,
            task_contract_hash=task_contract_hash, prompt_stack_hash=prompt_stack_hash,
            metadata={"turns_used": result.turns_used, "error_count": len(result.errors)},
        )
        return result

    async def _dispatch_tool_call(
        self,
        *,
        call: ToolCall,
        session_id: str,
        turn_index: int,
        messages: list[dict[str, Any]],
        all_tool_results: list[ToolResult],
        errors: list[str],
        trace_events: list[dict[str, Any]],
        repair_failure_counts: dict[tuple[str, str], int],
        exhausted_retry_fingerprints: dict[tuple[str, str], str],
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str],
        allowed_tools: list[str] | None = None,
        allowed_tool_permissions: list[str] | None = None,
        tool_result_cache: dict[str, ToolResult] | None = None,
    ) -> None:
        """Dispatch one tool call and record results."""
        cache_key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
        if tool_result_cache is not None and cache_key in tool_result_cache:
            cached = tool_result_cache[cache_key]
            self._record_trace_event(
                trace_events, "tool.cached", session_id,
                turn=turn_index + 1, status="cached",
                tool_name=call.name, tool_call_id=call.id,
                attributes={"cache_key": cache_key},
            )
            cached_result = ToolResult(
                call.name, cached.content, status=cached.status,
                tool_call_id=call.id, error=cached.error,
                metadata={**cached.metadata, "from_cache": True},
            )
            all_tool_results.append(cached_result)
            if self.state is not None:
                self.state.record_tool_call(
                    session_id, call.name, call.arguments,
                    result=cached.content, status=cached.status,
                    error=cached.error, call_id=call.id or None,
                )
            tool_feedback = self._compact_feedback(self._tool_feedback_content(cached_result))
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": tool_feedback})
            return
        session_counts = self._session_tool_counts.setdefault(session_id, {})
        session_counts[call.name] = session_counts.get(call.name, 0) + 1
        if session_counts[call.name] > self._MAX_SAME_TOOL_PER_SESSION:
            error = f"Tool '{call.name}' rate limit exceeded: {session_counts[call.name]} calls, max={self._MAX_SAME_TOOL_PER_SESSION} per session"
            logger.warning(error)
            tool_result = ToolResult(
                call.name,
                json.dumps({"error": error}, ensure_ascii=False),
                status="blocked",
                tool_call_id=call.id,
                error=error,
                metadata={"rate_limited": True, "tool_count": session_counts[call.name]},
            )
            self._record_trace_event(
                trace_events, "tool.rate_limited", session_id,
                turn=turn_index + 1, status="blocked",
                tool_name=call.name, tool_call_id=call.id,
                attributes={"tool_count": session_counts[call.name], "limit": self._MAX_SAME_TOOL_PER_SESSION},
            )
            all_tool_results.append(tool_result)
            errors.append(error)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": self._compact_feedback(self._tool_feedback_content(tool_result))})
            if self.state is not None:
                self.state.record_tool_call(
                    session_id, call.name, call.arguments,
                    result=tool_result.content, status=tool_result.status,
                    error=tool_result.error, call_id=call.id or None,
                )
            return
        cb_result = self._check_circuit_breaker(session_id, call.name)
        if cb_result is not None:
            logger.warning(cb_result)
            tool_result = ToolResult(
                call.name,
                json.dumps({"error": cb_result}, ensure_ascii=False),
                status="blocked",
                tool_call_id=call.id,
                error=cb_result,
                metadata={"circuit_breaker": True},
            )
            self._record_trace_event(
                trace_events, "tool.circuit_breaker", session_id,
                turn=turn_index + 1, status="blocked",
                tool_name=call.name, tool_call_id=call.id,
                attributes={"threshold": AgentLoop._CIRCUIT_BREAKER_THRESHOLD},
            )
            all_tool_results.append(tool_result)
            errors.append(cb_result)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": self._compact_feedback(self._tool_feedback_content(tool_result))})
            if self.state is not None:
                self.state.record_tool_call(
                    session_id, call.name, call.arguments,
                    result=tool_result.content, status=tool_result.status,
                    error=tool_result.error, call_id=call.id or None,
                )
            return
        self._record_trace_event(
            trace_events, "tool.request", session_id,
            turn=turn_index + 1, status="started",
            tool_name=call.name, tool_call_id=call.id,
            attributes={"arguments": call.arguments, "gen_ai.operation.name": "execute_tool"},
        )
        tool_result = self._maybe_block_exhausted_tool_retry(
            call, exhausted_retry_fingerprints, exhausted_shape_fingerprints,
        )
        if tool_result is None:
            tool_result = await self.dispatcher.dispatch(
                call,
                ToolContext(
                    session_id=session_id, workspace=self.workspace,
                    allowed_tools=allowed_tools,
                    allowed_tool_permissions=allowed_tool_permissions,
                    hooks=self.hooks, state=self.state,
                ),
            )
        self._apply_tool_failure_retry_budget(
            call, tool_result, repair_failure_counts,
            exhausted_retry_fingerprints, exhausted_shape_fingerprints,
        )
        tool_result_event = self._record_trace_event(
            trace_events, "tool.result", session_id,
            turn=turn_index + 1, status=tool_result.status,
            tool_name=tool_result.tool_name, tool_call_id=tool_result.tool_call_id,
            attributes={
                "failed": tool_result.failed, "metadata": tool_result.metadata,
                "error": tool_result.error, "gen_ai.operation.name": "execute_tool",
            },
        )
        self._record_schema_repair_hint_event(
            trace_events, session_id, turn=turn_index + 1,
            tool_result=tool_result,
            parent_event_id=str(tool_result_event.get("event_id", "")),
        )
        all_tool_results.append(tool_result)
        if tool_result_cache is not None and not tool_result.failed:
            tool_result_cache[cache_key] = tool_result
        if self.state is not None:
            self.state.record_tool_call(
                session_id, call.name, call.arguments,
                result=tool_result.content, status=tool_result.status,
                error=tool_result.error, call_id=call.id or None,
            )
        if tool_result.failed:
            errors.append(tool_result.error or tool_result.content)
            self._record_tool_failure(session_id, call.name)
        if self.evidence_ledger is not None:
            evidence_refs: list[str] = []
            for extracted in self.evidence_extractor.extract(tool_result):
                record = self.evidence_ledger.record_claim(
                    session_id=session_id, claim=extracted.claim,
                    source_type=extracted.source_type, source_ref=extracted.source_ref,
                    metadata=extracted.metadata,
                )
                evidence_refs.append(record.id)
            if evidence_refs:
                tool_result.metadata["evidence_refs"] = evidence_refs
        tool_feedback = self._compact_feedback(self._tool_feedback_content(tool_result))
        messages.append({
            "role": "tool", "tool_call_id": call.id,
            "name": call.name, "content": tool_feedback,
        })
        if self.state is not None:
            self.state.append_message(
                session_id, "tool", tool_feedback,
                {"tool": call.name, "tool_call_id": call.id},
            )

    async def _dispatch_tool_calls_batch(
        self,
        *,
        calls: list[ToolCall],
        session_id: str,
        turn_index: int,
        messages: list[dict[str, Any]],
        all_tool_results: list[ToolResult],
        errors: list[str],
        trace_events: list[dict[str, Any]],
        repair_failure_counts: dict[tuple[str, str], int],
        exhausted_retry_fingerprints: dict[tuple[str, str], str],
        exhausted_shape_fingerprints: dict[tuple[str, str, str], str],
        allowed_tools: list[str] | None = None,
        allowed_tool_permissions: list[str] | None = None,
        tool_result_cache: dict[str, ToolResult] | None = None,
        total_tool_calls: int = 0,
    ) -> int:
        """Dispatch tool calls concurrently: read-only calls in parallel, then write calls sequentially."""
        read_only_calls: list[ToolCall] = []
        write_calls: list[ToolCall] = []

        for call in calls:
            spec = self.registry.get(call.name)
            if spec is not None and spec.side_effect == "read":
                read_only_calls.append(call)
            else:
                write_calls.append(call)

        async def _dispatch_one(call: ToolCall) -> None:
            nonlocal total_tool_calls
            total_tool_calls += 1
            if total_tool_calls > self.profile.max_session_tool_calls:
                reason = f"Session tool call limit exceeded: {total_tool_calls} calls, max={self.profile.max_session_tool_calls}"
                errors.append(reason)
                self._record_trace_event(
                    trace_events, "tool.session_limit", session_id,
                    turn=turn_index + 1, status="blocked",
                    attributes={"total_tool_calls": total_tool_calls, "limit": self.profile.max_session_tool_calls},
                )
                return
            await self._dispatch_tool_call(
                call=call,
                session_id=session_id,
                turn_index=turn_index,
                messages=messages,
                all_tool_results=all_tool_results,
                errors=errors,
                trace_events=trace_events,
                repair_failure_counts=repair_failure_counts,
                exhausted_retry_fingerprints=exhausted_retry_fingerprints,
                exhausted_shape_fingerprints=exhausted_shape_fingerprints,
                allowed_tools=allowed_tools,
                allowed_tool_permissions=allowed_tool_permissions,
                tool_result_cache=tool_result_cache,
            )

        if read_only_calls:
            self._record_trace_event(
                trace_events, "tool.batch", session_id,
                turn=turn_index + 1, status="started",
                attributes={"concurrent_count": len(read_only_calls), "sequential_count": len(write_calls)},
            )
            await asyncio.gather(*[_dispatch_one(call) for call in read_only_calls])

        for call in write_calls:
            await _dispatch_one(call)

        return total_tool_calls

    def _check_circuit_breaker(self, session_id: str, tool_name: str) -> str | None:
        """Return error message if tool is circuit-broken, else None."""
        now = time.monotonic()
        failures = self._session_tool_failures.get(session_id, {}).get(tool_name, [])
        window_start = now - AgentLoop._CIRCUIT_BREAKER_WINDOW
        recent = [t for t in failures if t >= window_start]
        if len(recent) >= AgentLoop._CIRCUIT_BREAKER_THRESHOLD:
            last_failure = max(recent)
            if now - last_failure < AgentLoop._CIRCUIT_BREAKER_COOLDOWN:
                return (
                    f"Tool '{tool_name}' is temporarily unavailable due to repeated failures "
                    f"({len(recent)} in the last {AgentLoop._CIRCUIT_BREAKER_WINDOW}s). "
                    f"Try a different approach or return blocked."
                )
        return None

    def _record_tool_failure(self, session_id: str, tool_name: str) -> None:
        """Record a tool failure for circuit breaker tracking."""
        session_failures = self._session_tool_failures.setdefault(session_id, {})
        tool_failures = session_failures.setdefault(tool_name, [])
        now = time.monotonic()
        window_start = now - AgentLoop._CIRCUIT_BREAKER_WINDOW
        tool_failures[:] = [t for t in tool_failures if t >= window_start]
        tool_failures.append(now)

    def _run_behavior_gates(
        self,
        *,
        session_id: str,
        final_text: str,
        tool_results: list[Any],
        artifacts: list[Any],
        evidence: list[Any],
    ) -> list[str]:
        """Run behavior-rules quality gates and return a list of error messages."""
        gate_errors: list[str] = []
        # Behavior gates are evaluated lazily to avoid heavy import overhead
        # when the feature is disabled.
        try:
            from metis.behavior.registry import BehaviorRulesRegistry
            from metis.behavior.builtin import build_behavior_rules_config

            registry = BehaviorRulesRegistry(build_behavior_rules_config())
            for gate_spec in registry.get_gate_specs():
                try:
                    result = gate_spec.handler({
                        "session_id": session_id,
                        "final_text": final_text,
                        "tool_results": tool_results,
                        "artifacts": artifacts,
                        "evidence": evidence,
                    })
                    if not result.passed and gate_spec.failure_policy == "fail":
                        gate_errors.append(f"[behavior gate: {result.name}] {result.message}")
                    elif not result.passed:
                        # warn policy — log but do not block
                        logger.warning("Behavior gate '%s' warned: %s", result.name, result.message)
                except Exception as exc:
                    logger.warning("Behavior gate '%s' crashed: %s", gate_spec.name, exc)
        except Exception as exc:
            logger.debug("Behavior gates skipped: %s", exc)
        return gate_errors

    @staticmethod
    def _turn_signature(response: NormalizedResponse) -> str:
        """Generate a compact signature for loop detection."""
        if response.tool_calls:
            names = ",".join(sorted(call.name for call in response.tool_calls))
            args_hashes = [
                f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
                for call in response.tool_calls
            ]
            return f"tools:{names}|args:{','.join(args_hashes)}"
        return f"text:{response.content or ''}"

    @staticmethod
    def _detect_response_loop(signatures: list[str], threshold: int = 3) -> bool:
        """Detect if the same response pattern has repeated threshold times."""
        if len(signatures) < threshold:
            return False
        return len(set(signatures[-threshold:])) == 1
