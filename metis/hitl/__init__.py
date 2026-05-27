"""Human-in-the-Loop (HITL) approval system for Metis Agent Harness.

Provides configurable approval gates that intercept tool calls before execution,
requiring human confirmation for destructive, credential, or network operations.
"""

from __future__ import annotations

from metis.hitl.core import (
    HITLApprover,
    HITLConfig,
    build_hitl_approver,
    register_hitl_hooks,
)
from metis.hitl.models import ApprovalRequest, ApprovalStatus
from metis.hitl.rules import ApprovalRule, default_approval_rules
from metis.hitl.store import ApprovalStore

__all__ = [
    "ApprovalRequest",
    "ApprovalRule",
    "ApprovalStatus",
    "ApprovalStore",
    "HITLApprover",
    "HITLConfig",
    "build_hitl_approver",
    "default_approval_rules",
    "register_hitl_hooks",
]
