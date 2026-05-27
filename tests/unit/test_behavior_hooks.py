"""Tests for behavior-rules hook handlers."""

from __future__ import annotations

import pytest

from metis.behavior.hooks import (
    behavior_checkpoint_handler,
    behavior_error_auto_repair_handler,
    behavior_contract_violation_handler,
)


class TestBehaviorCheckpointHandler:
    def test_adds_checkpoint_id(self) -> None:
        ctx = {"session_id": "s1", "turn": 3, "phase": "turn.start", "metadata": {}}
        result = behavior_checkpoint_handler(ctx)
        assert "checkpoint_id" in result
        assert "behavior.checkpoint:s1:3:turn.start" in result["checkpoint_id"]


class TestBehaviorErrorAutoRepairHandler:
    def test_marks_eligible_for_tool_failure(self) -> None:
        ctx = {"error": "tool failed", "category": "tool_failure", "session_id": "s1"}
        result = behavior_error_auto_repair_handler(ctx)
        assert result["auto_repair_eligible"] is True
        assert result["auto_repair_recommended"] is True

    def test_marks_not_eligible_for_fatal_error(self) -> None:
        ctx = {"error": "oom", "category": "resource_exhausted", "session_id": "s1"}
        result = behavior_error_auto_repair_handler(ctx)
        assert result["auto_repair_eligible"] is False
        assert result["auto_repair_recommended"] is False


class TestBehaviorContractViolationHandler:
    def test_records_violation(self) -> None:
        ctx = {
            "violation_type": "placeholder_detected",
            "session_id": "s1",
            "details": {"marker": "TODO"},
        }
        result = behavior_contract_violation_handler(ctx)
        assert "behavior_violation" in result
        assert result["behavior_violation"]["type"] == "placeholder_detected"
