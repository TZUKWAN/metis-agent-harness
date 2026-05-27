"""Shared HITL data models."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    """A pending or resolved approval request."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    status: ApprovalStatus
    reason: str = ""
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
