"""Integration tests for HITL Web API endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from metis.app.hitl_api import router as hitl_router, set_hitl_store
from metis.app.hitl_schemas import HitlRequestItem
from metis.app.manifest import AgentAppManifest
from metis.app.web import create_app
from metis.hitl.models import ApprovalRequest, ApprovalStatus
from metis.hitl.store import ApprovalStore


@pytest.fixture
def hitl_store() -> ApprovalStore:
    return ApprovalStore()


@pytest.fixture
def client(hitl_store: ApprovalStore) -> TestClient:
    """Create a TestClient with HITL enabled and store initialized."""
    manifest = AgentAppManifest(
        name="Test Agent",
        hitl_enabled=True,
        hitl_timeout_seconds=5.0,
    )
    app = create_app(manifest)
    # Override the lifespan-created store with our test fixture
    set_hitl_store(hitl_store)
    return TestClient(app)


def test_hitl_pending_empty(client: TestClient) -> None:
    """GET /hitl/pending returns empty list when no requests."""
    response = client.get("/api/v1/hitl/pending")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["requests"] == []


def test_hitl_pending_with_requests(client: TestClient, hitl_store: ApprovalStore) -> None:
    """GET /hitl/pending returns pending requests."""
    req = ApprovalRequest(
        id="req-001",
        tool_name="file_write",
        arguments={"path": "/tmp/test.txt", "content": "hello"},
        status=ApprovalStatus.PENDING,
    )
    hitl_store.add(req)

    response = client.get("/api/v1/hitl/pending")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["requests"]) == 1
    assert data["requests"][0]["request_id"] == "req-001"
    assert data["requests"][0]["tool_name"] == "file_write"
    assert data["requests"][0]["status"] == "pending"


def test_hitl_approve(client: TestClient, hitl_store: ApprovalStore) -> None:
    """POST /hitl/{id}/approve resolves a pending request."""
    req = ApprovalRequest(
        id="req-002",
        tool_name="shell_exec",
        arguments={"command": "ls"},
        status=ApprovalStatus.PENDING,
    )
    hitl_store.add(req)

    response = client.post("/api/v1/hitl/req-002/approve", json={"reason": "Looks safe"})
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-002"
    assert data["status"] == "approved"
    assert "Looks safe" in data["reason"]

    # Verify store state
    updated = hitl_store.get("req-002")
    assert updated is not None
    assert updated.status == ApprovalStatus.APPROVED


def test_hitl_deny(client: TestClient, hitl_store: ApprovalStore) -> None:
    """POST /hitl/{id}/deny rejects a pending request."""
    req = ApprovalRequest(
        id="req-003",
        tool_name="network_post",
        arguments={"url": "http://example.com"},
        status=ApprovalStatus.PENDING,
    )
    hitl_store.add(req)

    response = client.post("/api/v1/hitl/req-003/deny")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "req-003"
    assert data["status"] == "denied"

    updated = hitl_store.get("req-003")
    assert updated is not None
    assert updated.status == ApprovalStatus.DENIED


def test_hitl_approve_not_found(client: TestClient) -> None:
    """Approving a non-existent request returns 404."""
    response = client.post("/api/v1/hitl/nonexistent/approve")
    assert response.status_code == 404


def test_hitl_approve_already_resolved(client: TestClient, hitl_store: ApprovalStore) -> None:
    """Approving an already-resolved request returns 400."""
    req = ApprovalRequest(
        id="req-004",
        tool_name="file_read",
        arguments={"path": "/tmp/foo"},
        status=ApprovalStatus.APPROVED,
    )
    hitl_store.add(req)

    response = client.post("/api/v1/hitl/req-004/approve")
    assert response.status_code == 400


def test_hitl_history(client: TestClient, hitl_store: ApprovalStore) -> None:
    """GET /hitl/history returns all requests."""
    hitl_store.add(ApprovalRequest(id="r1", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))
    hitl_store.add(ApprovalRequest(id="r2", tool_name="b", arguments={}, status=ApprovalStatus.PENDING))

    # Approve one
    req = hitl_store.get("r1")
    assert req is not None
    req.status = ApprovalStatus.APPROVED
    hitl_store.update(req)

    response = client.get("/api/v1/hitl/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["requests"]) == 2


def test_hitl_history_filter(client: TestClient, hitl_store: ApprovalStore) -> None:
    """GET /hitl/history?status=pending filters correctly."""
    hitl_store.add(ApprovalRequest(id="r3", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))
    req = hitl_store.get("r3")
    assert req is not None
    req.status = ApprovalStatus.APPROVED
    hitl_store.update(req)
    hitl_store.add(ApprovalRequest(id="r4", tool_name="b", arguments={}, status=ApprovalStatus.PENDING))

    response = client.get("/api/v1/hitl/history?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["requests"][0]["request_id"] == "r4"
    assert data["filter_status"] == "pending"


def test_hitl_history_limit(client: TestClient, hitl_store: ApprovalStore) -> None:
    """GET /hitl/history?limit=1 respects limit."""
    for i in range(5):
        hitl_store.add(ApprovalRequest(id=f"r{i}", tool_name="t", arguments={}, status=ApprovalStatus.PENDING))

    response = client.get("/api/v1/hitl/history?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_hitl_websocket_pending_list(client: TestClient, hitl_store: ApprovalStore) -> None:
    """WebSocket /hitl/stream sends pending list on connect."""
    hitl_store.add(ApprovalRequest(id="ws-1", tool_name="file_write", arguments={"path": "/x"}, status=ApprovalStatus.PENDING))

    with client.websocket_connect("/api/v1/hitl/stream") as ws:
        data = ws.receive_json()
        assert data["type"] == "pending_list"
        assert data["count"] == 1
        assert data["requests"][0]["request_id"] == "ws-1"


def test_hitl_websocket_ping_pong(client: TestClient) -> None:
    """WebSocket responds to ping with pong."""
    with client.websocket_connect("/api/v1/hitl/stream") as ws:
        # Receive initial pending_list broadcast
        _ = ws.receive_json()
        ws.send_text("ping")
        data = ws.receive_text()
        assert data == "pong"


def test_hitl_risk_level_mapping(client: TestClient, hitl_store: ApprovalStore) -> None:
    """Risk levels are correctly mapped from rule names."""
    from metis.app.hitl_schemas import _risk_level_from_rule

    assert _risk_level_from_rule("destructive") == "high"
    assert _risk_level_from_rule("credential") == "high"
    assert _risk_level_from_rule("network") == "medium"
    assert _risk_level_from_rule("read_only") == "low"
    assert _risk_level_from_rule("") == "low"


def test_hitl_store_wait_for_resolved(hitl_store: ApprovalStore) -> None:
    """wait_for returns immediately if request is already resolved."""
    req = ApprovalRequest(
        id="wait-1",
        tool_name="t",
        arguments={},
        status=ApprovalStatus.APPROVED,
    )
    hitl_store.add(req)

    result = asyncio.run(hitl_store.wait_for("wait-1", timeout=1.0))
    assert result is not None
    assert result.status == ApprovalStatus.APPROVED


def test_hitl_store_wait_for_timeout(hitl_store: ApprovalStore) -> None:
    """wait_for sets TIMEOUT status on timeout."""
    req = ApprovalRequest(id="wait-2", tool_name="t", arguments={}, status=ApprovalStatus.PENDING)
    hitl_store.add(req)

    result = asyncio.run(hitl_store.wait_for("wait-2", timeout=0.1))
    assert result is not None
    assert result.status == ApprovalStatus.TIMEOUT


def test_hitl_store_listener_notify(hitl_store: ApprovalStore) -> None:
    """Listeners are called when a request is added."""
    called_with: list[Any] = []

    def listener(req: ApprovalRequest) -> None:
        called_with.append(req)

    hitl_store.add_listener(listener)
    req = ApprovalRequest(id="l1", tool_name="t", arguments={}, status=ApprovalStatus.PENDING)
    hitl_store.add(req)

    assert len(called_with) == 1
    assert called_with[0].id == "l1"


def test_hitl_store_listener_remove(hitl_store: ApprovalStore) -> None:
    """Removed listeners are not called."""
    called: list[Any] = []

    def listener(req: ApprovalRequest) -> None:
        called.append(req)

    hitl_store.add_listener(listener)
    hitl_store.remove_listener(listener)
    hitl_store.add(ApprovalRequest(id="l2", tool_name="t", arguments={}, status=ApprovalStatus.PENDING))

    assert len(called) == 0
