"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000, description="User message to the agent")
    session_id: str = Field(default="", max_length=128, description="Session identifier")

    @field_validator("message")
    @classmethod
    def message_must_have_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must contain non-whitespace content")
        return stripped


class ChatResponse(BaseModel):
    session_id: str
    response: str
    status: str
    errors: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail

    class ErrorDetail(BaseModel):
        code: int
        message: str


class SessionInfo(BaseModel):
    id: str
    title: str
    model: str
    message_count: int
    tool_call_count: int = 0
    evidence_count: int = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


class HealthResponse(BaseModel):
    status: str
    name: str
    version: str
    model: str
    uptime_seconds: float
    checks: dict[str, Any]
