"""Pydantic schemas for HITL Web API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class HitlRequestItem(BaseModel):
    """A single approval request for API serialization."""

    request_id: str = Field(..., description="Unique request identifier")
    tool_name: str = Field(..., description="Name of the tool being called")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    status: str = Field(..., description="pending/approved/denied/timeout")
    reason: str = Field(default="", description="Approval or denial reason")
    created_at: str = Field(..., description="ISO timestamp when the request was created")
    resolved_at: str | None = Field(default=None, description="ISO timestamp when resolved")
    risk_level: str = Field(default="medium", description="low/medium/high based on rule type")

    @classmethod
    def from_approval_request(
        cls,
        request: Any,
        risk_level: str = "medium",
    ) -> "HitlRequestItem":
        """Build from an ApprovalRequest dataclass instance."""
        from metis.hitl.models import ApprovalRequest

        if isinstance(request, ApprovalRequest):
            return cls(
                request_id=request.id,
                tool_name=request.tool_name,
                arguments=request.arguments,
                status=request.status.value,
                reason=request.reason,
                created_at=_format_ts(request.created_at),
                resolved_at=_format_ts(request.resolved_at) if request.resolved_at else None,
                risk_level=risk_level,
            )
        # Fallback for plain dict
        return cls(
            request_id=str(request.get("id", "")),
            tool_name=str(request.get("tool_name", "")),
            arguments=request.get("arguments", {}),
            status=str(request.get("status", "pending")),
            reason=str(request.get("reason", "")),
            created_at=_format_ts(request.get("created_at")),
            resolved_at=_format_ts(request.get("resolved_at")) if request.get("resolved_at") else None,
            risk_level=risk_level,
        )


class HitlPendingResponse(BaseModel):
    """Response for GET /hitl/pending."""

    requests: list[HitlRequestItem] = Field(default_factory=list)
    count: int = Field(default=0, description="Total pending count")


class HitlActionRequest(BaseModel):
    """Request body for POST /hitl/{request_id}/approve or /deny."""

    reason: str = Field(default="", description="Optional reason for the action")


class HitlActionResponse(BaseModel):
    """Response for POST /hitl/{request_id}/approve or /deny."""

    request_id: str
    status: str
    reason: str = ""
    resolved_at: str | None = None


class HitlHistoryResponse(BaseModel):
    """Response for GET /hitl/history."""

    requests: list[HitlRequestItem] = Field(default_factory=list)
    total: int = Field(default=0)
    filter_status: str | None = Field(default=None)


def _format_ts(ts: float | None) -> str:
    """Format a Unix timestamp as ISO string."""
    if ts is None:
        return ""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return ""


def _risk_level_from_rule(rule_name: str) -> str:
    """Map rule name to a risk level for UI display."""
    high_risk = {"destructive", "credential", "shell_dangerous", "external_publish"}
    medium_risk = {"network"}
    if rule_name in high_risk:
        return "high"
    if rule_name in medium_risk:
        return "medium"
    return "low"
