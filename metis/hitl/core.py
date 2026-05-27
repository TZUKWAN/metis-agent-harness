"""Core HITL approval logic and hook integration."""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.hitl.models import ApprovalRequest, ApprovalStatus
from metis.hitl.rules import ApprovalRule, default_approval_rules
from metis.hitl.store import ApprovalStore
from metis.tools.spec import ToolSpec

logger = logging.getLogger(__name__)


@dataclass
class HITLConfig:
    """Configuration for the HITL approval system."""

    enabled: bool = False
    rules: list[ApprovalRule] = field(default_factory=list)
    interactive: bool = True
    timeout_seconds: float = 300.0
    auto_approve_read_only: bool = True
    auto_approve_tools: list[str] = field(default_factory=list)
    auto_deny_tools: list[str] = field(default_factory=list)
    prompt_template: str = (
        "The agent wants to call '{tool_name}' with arguments: {args}\n"
        "Approve? (yes/no): "
    )


class HITLApprover:
    """Evaluates tool calls against approval rules and manages human approval."""

    def __init__(
        self,
        config: HITLConfig | None = None,
        store: ApprovalStore | None = None,
        input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.config = config or HITLConfig()
        self.store = store or ApprovalStore()
        self._input_fn = input_fn or self._default_input
        self._rules = list(self.config.rules) if self.config.rules else default_approval_rules()

    def _default_input(self, prompt: str) -> str:
        return input(prompt)

    def requires_approval(self, tool_name: str, arguments: dict[str, Any], spec: ToolSpec | None) -> bool:
        """Check if a tool call requires human approval."""
        if not self.config.enabled:
            return False

        if tool_name in self.config.auto_approve_tools:
            return False
        if tool_name in self.config.auto_deny_tools:
            return True

        if spec is not None:
            if self.config.auto_approve_read_only and spec.side_effect == "read":
                return False

        for rule in self._rules:
            if rule.matches(tool_name, arguments, spec):
                return True

        return False

    async def request_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        spec: ToolSpec | None = None,
    ) -> ApprovalRequest:
        """Request approval for a tool call. Returns the resolved request."""
        request_id = str(uuid.uuid4())[:8]
        request = ApprovalRequest(
            id=request_id,
            tool_name=tool_name,
            arguments=arguments,
            status=ApprovalStatus.PENDING,
        )
        self.store.add(request)

        if self.config.interactive and sys.stdin.isatty():
            approved = await self._interactive_prompt(tool_name, arguments)
            request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
            request.resolved_at = asyncio.get_event_loop().time()
        else:
            # Non-interactive mode (e.g., web server): auto-approve read-only tools,
            # block and wait for write tools to be approved via API.
            if spec is not None and spec.side_effect == "read":
                logger.info("HITL auto-approving read-only tool %s in non-interactive mode.", tool_name)
                request.status = ApprovalStatus.APPROVED
                request.reason = "Auto-approved: read-only tool in non-interactive mode"
                request.resolved_at = asyncio.get_event_loop().time()
            else:
                logger.info("HITL approval required for %s in non-interactive mode; waiting for external approval.", tool_name)
                request.status = ApprovalStatus.PENDING
                request.reason = "Non-interactive mode: approval pending"
                self.store.update(request)

                resolved = await self.store.wait_for(
                    request.id,
                    timeout=self.config.timeout_seconds,
                )
                if resolved is not None:
                    request = resolved
                # wait_for handles TIMEOUT status internally

        self.store.update(request)
        return request

    async def _interactive_prompt(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Prompt the user for approval in an async-safe way."""
        prompt = self.config.prompt_template.format(
            tool_name=tool_name,
            args=arguments,
        )
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._input_fn, prompt),
                timeout=self.config.timeout_seconds,
            )
            return response.strip().lower() in {"y", "yes", "approve", "ok"}
        except asyncio.TimeoutError:
            logger.warning("HITL approval timed out for %s", tool_name)
            return False
        except Exception as exc:
            logger.warning("HITL prompt failed: %s", exc)
            return False


def register_hitl_hooks(hooks: HookBus, approver: HITLApprover) -> None:
    """Register HITL approval hooks on a HookBus."""

    async def _hitl_pre_dispatch(ctx: dict[str, Any]) -> dict[str, Any]:
        tool_name = ctx.get("tool", "")
        args = ctx.get("args", {})
        spec = ctx.get("spec")

        if not approver.requires_approval(tool_name, args, spec):
            return ctx

        request = await approver.request_approval(tool_name, args, spec)
        if request.status != ApprovalStatus.APPROVED:
            ctx["blocked"] = True
            ctx["block_reason"] = request.reason or f"HITL approval {request.status.value} for {tool_name}"
            ctx["hitl_request"] = request
        else:
            ctx["hitl_approved"] = True
            ctx["hitl_request"] = request

        return ctx

    hooks.register(EventType.TOOL_PRE_DISPATCH, _hitl_pre_dispatch, priority=10, name="hitl_approval")


def build_hitl_approver(
    manifest_data: dict[str, Any] | None = None,
    *,
    interactive: bool = True,
    store: ApprovalStore | None = None,
) -> HITLApprover:
    """Build a HITLApprover from manifest data or defaults."""
    data = manifest_data or {}
    enabled = data.get("hitl_enabled", False)

    config = HITLConfig(
        enabled=enabled,
        interactive=interactive,
        auto_approve_read_only=data.get("hitl_auto_approve_read_only", True),
        auto_approve_tools=data.get("hitl_auto_approve_tools", []),
        auto_deny_tools=data.get("hitl_auto_deny_tools", []),
        timeout_seconds=data.get("hitl_timeout_seconds", 300.0),
    )
    return HITLApprover(config=config, store=store)
