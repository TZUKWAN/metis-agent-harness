"""Tests for HITL core approval logic."""

from __future__ import annotations

import asyncio

import pytest

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.hitl.core import HITLApprover, HITLConfig, build_hitl_approver, register_hitl_hooks
from metis.hitl.models import ApprovalStatus
from metis.hitl.rules import ApprovalRule
from metis.tools.spec import ToolSpec


def test_requires_approval_disabled():
    approver = HITLApprover(config=HITLConfig(enabled=False))

    assert approver.requires_approval("delete_file", {}, None) is False


def test_requires_approval_auto_approve_tools():
    approver = HITLApprover(config=HITLConfig(enabled=True, auto_approve_tools=["read_file"]))
    destructive_spec = ToolSpec("delete_file", "Delete", {"type": "object"}, handler=lambda a, c: "", side_effect="destructive")

    assert approver.requires_approval("read_file", {}, None) is False
    assert approver.requires_approval("delete_file", {}, destructive_spec) is True


def test_requires_approval_auto_deny_tools():
    approver = HITLApprover(config=HITLConfig(enabled=True, auto_deny_tools=["delete_file"]))

    assert approver.requires_approval("delete_file", {}, None) is True
    assert approver.requires_approval("read_file", {}, None) is False


def test_requires_approval_read_only_tools():
    read_spec = ToolSpec("read", "Read", {"type": "object"}, handler=lambda a, c: "", side_effect="read")
    write_spec = ToolSpec("write", "Write", {"type": "object"}, handler=lambda a, c: "", side_effect="write")
    approver = HITLApprover(config=HITLConfig(enabled=True, auto_approve_read_only=True))

    assert approver.requires_approval("read", {}, read_spec) is False
    # 'write' side_effect alone does not trigger default rules (only destructive/network/credential/shell_dangerous/external_publish)
    assert approver.requires_approval("write", {}, write_spec) is False


def test_requires_approval_with_rules():
    rule = ApprovalRule(name="test", tool_names=["dangerous_op"])
    approver = HITLApprover(config=HITLConfig(enabled=True, rules=[rule]))

    assert approver.requires_approval("dangerous_op", {}, None) is True
    assert approver.requires_approval("safe_op", {}, None) is False


async def test_request_approval_non_interactive_pending():
    """Non-interactive mode: write tools without spec remain PENDING for external resolution."""
    approver = HITLApprover(config=HITLConfig(enabled=True, interactive=False))

    request = await approver.request_approval("delete_file", {"path": "/tmp/x"})

    assert request.status == ApprovalStatus.PENDING
    assert request.tool_name == "delete_file"


async def test_request_approval_non_interactive_auto_approves_read_only():
    """Non-interactive mode: read-only tools are auto-approved."""
    approver = HITLApprover(config=HITLConfig(enabled=True, interactive=False))
    read_spec = ToolSpec("read_file", "Read", {"type": "object"}, handler=lambda a, c: "", side_effect="read")

    request = await approver.request_approval("read_file", {"path": "/tmp/x"}, spec=read_spec)

    assert request.status == ApprovalStatus.APPROVED


async def test_request_approval_interactive_approves(monkeypatch):
    approver = HITLApprover(
        config=HITLConfig(enabled=True, interactive=True),
        input_fn=lambda prompt: "yes",
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    request = await approver.request_approval("delete_file", {"path": "/tmp/x"})

    assert request.status == ApprovalStatus.APPROVED


async def test_request_approval_interactive_denies(monkeypatch):
    approver = HITLApprover(
        config=HITLConfig(enabled=True, interactive=True),
        input_fn=lambda prompt: "no",
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    request = await approver.request_approval("delete_file", {"path": "/tmp/x"})

    assert request.status == ApprovalStatus.DENIED


async def test_request_approval_interactive_timeout(monkeypatch):
    approver = HITLApprover(
        config=HITLConfig(enabled=True, interactive=True, timeout_seconds=0.01),
        input_fn=lambda prompt: asyncio.sleep(10) or "yes",
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    request = await approver.request_approval("delete_file", {"path": "/tmp/x"})

    assert request.status == ApprovalStatus.DENIED


async def test_hitl_hook_blocks_when_pending():
    """Non-interactive mode: destructive tools are blocked as PENDING (not denied)."""
    hooks = HookBus()
    approver = HITLApprover(
        config=HITLConfig(enabled=True, interactive=False),
    )
    register_hitl_hooks(hooks, approver)
    destructive_spec = ToolSpec("delete_file", "Delete", {"type": "object"}, handler=lambda a, c: "", side_effect="destructive")

    result = await hooks.emit_async(
        EventType.TOOL_PRE_DISPATCH,
        {"tool": "delete_file", "args": {"path": "/tmp/x"}, "spec": destructive_spec},
    )

    assert result.get("blocked") is True
    assert "pending" in result.get("block_reason", "").lower()
    assert result.get("hitl_request") is not None


async def test_hitl_hook_allows_when_approved(monkeypatch):
    hooks = HookBus()
    approver = HITLApprover(
        config=HITLConfig(enabled=True, interactive=True),
        input_fn=lambda prompt: "yes",
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    register_hitl_hooks(hooks, approver)
    destructive_spec = ToolSpec("delete_file", "Delete", {"type": "object"}, handler=lambda a, c: "", side_effect="destructive")

    result = await hooks.emit_async(
        EventType.TOOL_PRE_DISPATCH,
        {"tool": "delete_file", "args": {"path": "/tmp/x"}, "spec": destructive_spec},
    )

    assert result.get("blocked") is not True
    assert result.get("hitl_approved") is True


async def test_hitl_hook_ignores_safe_tools():
    hooks = HookBus()
    read_spec = ToolSpec("read_file", "Read", {"type": "object"}, handler=lambda a, c: "", side_effect="read")
    approver = HITLApprover(config=HITLConfig(enabled=True, auto_approve_read_only=True))
    register_hitl_hooks(hooks, approver)

    result = await hooks.emit_async(
        EventType.TOOL_PRE_DISPATCH,
        {"tool": "read_file", "args": {"path": "/tmp/x"}, "spec": read_spec},
    )

    assert result.get("blocked") is not True
    assert "hitl_request" not in result


def test_build_hitl_approver_from_manifest():
    approver = build_hitl_approver({
        "hitl_enabled": True,
        "hitl_auto_approve_read_only": False,
        "hitl_timeout_seconds": 60.0,
    })

    assert approver.config.enabled is True
    assert approver.config.auto_approve_read_only is False
    assert approver.config.timeout_seconds == 60.0


def test_build_hitl_approver_disabled_by_default():
    approver = build_hitl_approver({})

    assert approver.config.enabled is False
