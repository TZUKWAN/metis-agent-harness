"""HITL Web API — endpoints for pending approval management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from metis.app.hitl_schemas import (
    HitlActionRequest,
    HitlActionResponse,
    HitlHistoryResponse,
    HitlPendingResponse,
    HitlRequestItem,
    _risk_level_from_rule,
)
from metis.hitl.models import ApprovalStatus
from metis.hitl.store import ApprovalStore
from metis.logging import get_logger

logger = get_logger("hitl.api")

# Global store instance — shared across the app
_hitl_store: ApprovalStore | None = None


def set_hitl_store(store: ApprovalStore) -> None:
    """Set the global HITL store for the API."""
    global _hitl_store
    _hitl_store = store


def get_hitl_store() -> ApprovalStore:
    """Get the global HITL store."""
    if _hitl_store is None:
        raise HTTPException(status_code=503, detail="HITL store not initialized")
    return _hitl_store


router = APIRouter(prefix="/hitl", tags=["hitl"])


@router.get("/pending")
async def list_pending() -> HitlPendingResponse:
    """List all pending approval requests."""
    store = get_hitl_store()
    pending = store.list_pending()
    items = [
        HitlRequestItem.from_approval_request(r, risk_level=_risk_level_from_rule(r.reason))
        for r in pending
    ]
    # Sort by created_at descending
    items.sort(key=lambda x: x.created_at, reverse=True)
    return HitlPendingResponse(requests=items, count=len(items))


@router.post("/{request_id}/approve")
async def approve_request(request_id: str, body: HitlActionRequest | None = None) -> HitlActionResponse:
    """Approve a pending HITL request."""
    store = get_hitl_store()
    request = store.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request is already {request.status.value}")

    request.status = ApprovalStatus.APPROVED
    request.reason = body.reason if body and body.reason else "Approved via web UI"
    store.update(request)

    logger.info("HITL request %s approved for tool %s", request_id, request.tool_name)
    return HitlActionResponse(
        request_id=request_id,
        status=ApprovalStatus.APPROVED.value,
        reason=request.reason,
    )


@router.post("/{request_id}/deny")
async def deny_request(request_id: str, body: HitlActionRequest | None = None) -> HitlActionResponse:
    """Deny a pending HITL request."""
    store = get_hitl_store()
    request = store.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request is already {request.status.value}")

    request.status = ApprovalStatus.DENIED
    request.reason = body.reason if body and body.reason else "Denied via web UI"
    store.update(request)

    logger.info("HITL request %s denied for tool %s", request_id, request.tool_name)
    return HitlActionResponse(
        request_id=request_id,
        status=ApprovalStatus.DENIED.value,
        reason=request.reason,
    )


@router.get("/history")
async def list_history(
    status: str | None = Query(default=None, description="Filter by status: pending/approved/denied/timeout"),
    limit: int = Query(default=50, ge=1, le=200),
) -> HitlHistoryResponse:
    """List approval history, optionally filtered by status."""
    store = get_hitl_store()
    items = store.list_history(status=status, limit=limit)
    return HitlHistoryResponse(
        requests=[HitlRequestItem.from_approval_request(r) for r in items],
        total=len(items),
        filter_status=status,
    )


# ---- WebSocket for real-time HITL notifications ----

_hitl_websockets: set[WebSocket] = set()


@router.websocket("/stream")
async def hitl_stream(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time HITL pending notifications.

    On connect, sends the current pending list.
    When new pending requests are created, pushes them to all connected clients.
    """
    await websocket.accept()
    _hitl_websockets.add(websocket)

    store = get_hitl_store()

    # Send current pending list on connect
    try:
        pending = store.list_pending()
        items = [
            HitlRequestItem.from_approval_request(r, risk_level=_risk_level_from_rule(r.reason))
            for r in pending
        ]
        await websocket.send_json({
            "type": "pending_list",
            "requests": [item.model_dump() for item in items],
            "count": len(items),
        })
    except Exception as exc:
        logger.debug("HITL WebSocket initial send error: %s", exc)

    async def _on_new_request(request: Any) -> None:
        """Callback invoked when a new approval request is added."""
        try:
            item = HitlRequestItem.from_approval_request(
                request, risk_level=_risk_level_from_rule(request.reason)
            )
            await websocket.send_json({
                "type": "new_pending",
                "request": item.model_dump(),
            })
        except Exception as exc:
            logger.debug("HITL WebSocket push error: %s", exc)

    store.add_listener(_on_new_request)

    try:
        while True:
            # Keep connection alive, handle client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("HITL WebSocket error: %s", exc)
    finally:
        _hitl_websockets.discard(websocket)
        store.remove_listener(_on_new_request)
