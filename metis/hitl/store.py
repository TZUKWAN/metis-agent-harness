"""In-memory storage for HITL approval requests."""

from __future__ import annotations

import asyncio
from typing import Any

from metis.hitl.models import ApprovalRequest, ApprovalStatus


class ApprovalStore:
    """Simple in-memory store for approval requests.

    Future versions may persist to SQLite or another backend.
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._listeners: list[Any] = []

    def add_listener(self, callback: Any) -> None:
        """Register a callback to be called when a new request is added."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Any) -> None:
        """Remove a previously registered callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, request: ApprovalRequest) -> None:
        """Notify all listeners of a new request."""
        for listener in list(self._listeners):
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(request))
                else:
                    listener(request)
            except Exception:
                pass

    def add(self, request: ApprovalRequest) -> None:
        """Add a new approval request."""
        self._requests[request.id] = request
        self._events[request.id] = asyncio.Event()
        self._notify_listeners(request)

    def get(self, request_id: str) -> ApprovalRequest | None:
        """Retrieve an approval request by ID."""
        return self._requests.get(request_id)

    def update(self, request: ApprovalRequest) -> None:
        """Update an existing approval request."""
        self._requests[request.id] = request
        event = self._events.get(request.id)
        if event is not None:
            event.set()

    async def wait_for(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> ApprovalRequest | None:
        """Wait asynchronously for an approval request to be resolved.

        Returns the request if resolved within timeout, or None if timed out.
        If the request is already resolved (not PENDING), returns immediately.
        """
        request = self._requests.get(request_id)
        if request is None:
            return None
        if request.status != ApprovalStatus.PENDING:
            return request

        event = self._events.get(request_id)
        if event is None:
            event = asyncio.Event()
            self._events[request_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Update request status to TIMEOUT
            request.status = ApprovalStatus.TIMEOUT
            request.reason = request.reason or "Approval timed out"
            self._requests[request_id] = request
            return request

        return self._requests.get(request_id)

    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        return [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]

    def list_all(self) -> list[ApprovalRequest]:
        """List all approval requests."""
        return list(self._requests.values())

    def list_history(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalRequest]:
        """List approval history, optionally filtered by status."""
        items = self.list_all()
        if status:
            items = [r for r in items if r.status.value == status]
        # Sort by created_at descending
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[:limit]

    def remove(self, request_id: str) -> bool:
        """Remove an approval request. Returns True if it existed."""
        if request_id in self._requests:
            del self._requests[request_id]
            self._events.pop(request_id, None)
            return True
        return False

    def clear(self) -> None:
        """Clear all approval requests."""
        self._requests.clear()
        self._events.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize store state to a dict."""
        return {
            "requests": [
                {
                    "id": r.id,
                    "tool_name": r.tool_name,
                    "arguments": r.arguments,
                    "status": r.status.value,
                    "reason": r.reason,
                    "created_at": r.created_at,
                    "resolved_at": r.resolved_at,
                }
                for r in self._requests.values()
            ]
        }
