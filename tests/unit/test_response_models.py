"""Tests for Pydantic response models."""

from __future__ import annotations


def test_chat_response_model():
    from metis.app.schemas import ChatResponse

    resp = ChatResponse(session_id="abc", response="hello", status="success")
    assert resp.session_id == "abc"
    assert resp.response == "hello"
    assert resp.status == "success"
    assert resp.errors == []


def test_chat_response_with_errors():
    from metis.app.schemas import ChatResponse

    resp = ChatResponse(session_id="abc", response="", status="error", errors=["timeout"])
    assert resp.errors == ["timeout"]


def test_error_response_model():
    from metis.app.schemas import ErrorResponse

    resp = ErrorResponse(error={"code": 429, "message": "Rate limit exceeded"})
    assert resp.error.code == 429
    assert resp.error.message == "Rate limit exceeded"


def test_session_info_model():
    from metis.app.schemas import SessionInfo

    info = SessionInfo(id="s1", title="Test", model="glm-4-flash", message_count=5)
    assert info.tool_call_count == 0
    assert info.evidence_count == 0


def test_session_list_response_model():
    from metis.app.schemas import SessionListResponse, SessionInfo

    resp = SessionListResponse(sessions=[
        SessionInfo(id="s1", title="A", model="m1", message_count=3),
        SessionInfo(id="s2", title="B", model="m2", message_count=7, tool_call_count=2),
    ])
    assert len(resp.sessions) == 2
    assert resp.sessions[1].tool_call_count == 2


def test_health_response_model():
    from metis.app.schemas import HealthResponse

    resp = HealthResponse(
        status="healthy",
        name="test-agent",
        version="1.0.0",
        model="glm-4-flash",
        uptime_seconds=123.4,
        checks={"provider": "ok"},
    )
    assert resp.status == "healthy"
    assert resp.checks["provider"] == "ok"


def test_error_response_serialization():
    from metis.app.schemas import ErrorResponse

    resp = ErrorResponse(error={"code": 500, "message": "Internal server error"})
    data = resp.model_dump()
    assert data == {"error": {"code": 500, "message": "Internal server error"}}


def test_chat_response_serialization():
    from metis.app.schemas import ChatResponse

    resp = ChatResponse(session_id="abc123", response="Done", status="success")
    data = resp.model_dump()
    assert data["session_id"] == "abc123"
    assert data["errors"] == []
