"""Hook handlers for behavior-rule automation.

These handlers are registered on the HookBus to enforce runtime policies
such as checkpoint logging, automatic error recovery, and contract-violation
reporting.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("metis.behavior.hooks")


def behavior_checkpoint_handler(context: dict[str, Any]) -> dict[str, Any]:
    """Log a behavior checkpoint for high-density observability (rule 5).

    The checkpoint is written as a trace event so it can be audited later.
    """
    session_id = context.get("session_id", "unknown")
    turn = context.get("turn", 0)
    phase = context.get("phase", "unknown")
    checkpoint_id = f"behavior.checkpoint:{session_id}:{turn}:{phase}"
    logger.debug("Behavior checkpoint: %s — %s", checkpoint_id, context.get("metadata", {}))
    context["checkpoint_id"] = checkpoint_id
    return context


def behavior_error_auto_repair_handler(context: dict[str, Any]) -> dict[str, Any]:
    """Attempt to classify and flag an error for auto-repair (rule 8).

    This handler does not perform the actual retry (that happens inside
    AgentLoop) — it records the error classification and sets a flag
    so downstream logic knows whether auto-repair is recommended.
    """
    error = str(context.get("error", ""))
    category = context.get("category", "unknown")
    session_id = context.get("session_id", "unknown")

    # Flag auto-repair eligibility by error category
    auto_repair_eligible = category in {
        "tool_failure",
        "parser_error",
        "schema_validation",
        "transient_network",
    }

    context["auto_repair_eligible"] = auto_repair_eligible
    context["auto_repair_recommended"] = auto_repair_eligible

    logger.info(
        "Behavior auto-repair check: session=%s category=%s eligible=%s",
        session_id,
        category,
        auto_repair_eligible,
    )
    return context


def behavior_contract_violation_handler(context: dict[str, Any]) -> dict[str, Any]:
    """Record a contract-violation event when deception is detected (rule 13).

    This is triggered by downstream integrity checks (e.g. placeholder detection,
    evidence mismatch) and escalates the violation to the trace log.
    """
    violation_type = context.get("violation_type", "unknown")
    session_id = context.get("session_id", "unknown")
    details = context.get("details", {})

    logger.warning(
        "Behavior contract violation: session=%s type=%s details=%s",
        session_id,
        violation_type,
        details,
    )

    # Mark the context so finalization gates can see it
    context["behavior_violation"] = {
        "type": violation_type,
        "details": details,
    }
    return context
