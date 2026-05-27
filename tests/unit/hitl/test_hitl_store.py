"""Tests for HITL approval store."""

from metis.hitl.models import ApprovalRequest, ApprovalStatus
from metis.hitl.store import ApprovalStore


def test_add_and_get_request():
    store = ApprovalStore()
    req = ApprovalRequest(id="r1", tool_name="delete", arguments={"path": "/x"}, status=ApprovalStatus.PENDING)

    store.add(req)

    assert store.get("r1") is req
    assert store.get("nonexistent") is None


def test_update_request():
    store = ApprovalStore()
    req = ApprovalRequest(id="r1", tool_name="delete", arguments={}, status=ApprovalStatus.PENDING)
    store.add(req)

    req.status = ApprovalStatus.APPROVED
    store.update(req)

    assert store.get("r1").status == ApprovalStatus.APPROVED


def test_list_pending():
    store = ApprovalStore()
    store.add(ApprovalRequest(id="r1", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))
    store.add(ApprovalRequest(id="r2", tool_name="b", arguments={}, status=ApprovalStatus.APPROVED))
    store.add(ApprovalRequest(id="r3", tool_name="c", arguments={}, status=ApprovalStatus.PENDING))

    pending = store.list_pending()

    assert len(pending) == 2
    assert {r.id for r in pending} == {"r1", "r3"}


def test_list_all():
    store = ApprovalStore()
    store.add(ApprovalRequest(id="r1", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))
    store.add(ApprovalRequest(id="r2", tool_name="b", arguments={}, status=ApprovalStatus.APPROVED))

    assert len(store.list_all()) == 2


def test_remove_request():
    store = ApprovalStore()
    store.add(ApprovalRequest(id="r1", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))

    assert store.remove("r1") is True
    assert store.get("r1") is None
    assert store.remove("r1") is False


def test_clear():
    store = ApprovalStore()
    store.add(ApprovalRequest(id="r1", tool_name="a", arguments={}, status=ApprovalStatus.PENDING))

    store.clear()

    assert store.list_all() == []


def test_to_dict():
    store = ApprovalStore()
    store.add(ApprovalRequest(id="r1", tool_name="delete", arguments={"path": "/x"}, status=ApprovalStatus.APPROVED, reason="ok"))

    data = store.to_dict()

    assert len(data["requests"]) == 1
    assert data["requests"][0]["id"] == "r1"
    assert data["requests"][0]["status"] == "approved"
    assert data["requests"][0]["reason"] == "ok"
