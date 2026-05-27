"""Tests for behavior-rules quality gates."""

from __future__ import annotations

import pytest

from metis.behavior.gates import (
    behavior_completeness_gate,
    behavior_no_deception_gate,
    behavior_research_verification_gate,
)


class TestBehaviorCompletenessGate:
    def test_passes_when_no_claims(self) -> None:
        gate = behavior_completeness_gate()
        result = gate.handler({
            "final_text": "Here is a summary of what was done.",
            "tool_results": [],
            "artifacts": [],
            "evidence": [],
        })
        assert result.passed is True

    def test_fails_when_test_mentioned_but_not_executed(self) -> None:
        gate = behavior_completeness_gate()
        result = gate.handler({
            "final_text": "I have tested the code thoroughly.",
            "tool_results": [],
            "artifacts": [],
            "evidence": [],
        })
        assert result.passed is False
        assert "test" in result.message.lower()

    def test_passes_when_tests_executed(self) -> None:
        gate = behavior_completeness_gate()
        result = gate.handler({
            "final_text": "I have tested the code thoroughly.",
            "tool_results": [{"tool_name": "run_shell", "content": "pytest passed"}],
            "artifacts": [],
            "evidence": [],
        })
        assert result.passed is True

    def test_fails_when_artifact_claimed_but_missing(self) -> None:
        gate = behavior_completeness_gate()
        result = gate.handler({
            "final_text": "I created `output.txt` for you.",
            "tool_results": [],
            "artifacts": [],
            "evidence": [],
        })
        assert result.passed is False
        assert "output.txt" in result.message


class TestBehaviorNoDeceptionGate:
    def test_passes_clean_text(self) -> None:
        gate = behavior_no_deception_gate()
        result = gate.handler({
            "final_text": "The implementation is complete. All tests pass.",
            "tool_results": [{"tool_name": "run_shell"}],
            "artifacts": [{"path": "/tmp/test.py"}],
        })
        assert result.passed is True

    def test_fails_on_placeholder_text(self) -> None:
        gate = behavior_no_deception_gate()
        result = gate.handler({
            "final_text": "Here is the implementation. TODO: add error handling.",
            "tool_results": [],
            "artifacts": [],
        })
        assert result.passed is False
        assert "TODO" in result.message

    def test_fails_on_simulated_data(self) -> None:
        gate = behavior_no_deception_gate()
        result = gate.handler({
            "final_text": "This is simulated data for demonstration purposes only.",
            "tool_results": [],
            "artifacts": [],
        })
        assert result.passed is False

    def test_warns_on_completion_without_evidence(self) -> None:
        gate = behavior_no_deception_gate()
        result = gate.handler({
            "final_text": "A" * 300 + " everything is completed successfully.",
            "tool_results": [],
            "artifacts": [],
        })
        assert result.passed is False
        assert "without" in result.message.lower() or "completion" in result.message.lower()


class TestBehaviorResearchVerificationGate:
    def test_passes_when_no_external_refs(self) -> None:
        gate = behavior_research_verification_gate()
        result = gate.handler({
            "final_text": "The code has been updated.",
            "tool_results": [],
        })
        assert result.passed is True

    def test_passes_when_research_done(self) -> None:
        gate = behavior_research_verification_gate()
        result = gate.handler({
            "final_text": "According to the official docs at https://example.com...",
            "tool_results": [{"tool_name": "web_fetch"}],
        })
        assert result.passed is True

    def test_warns_when_refs_without_research(self) -> None:
        gate = behavior_research_verification_gate()
        result = gate.handler({
            "final_text": "According to research shows that...",
            "tool_results": [{"tool_name": "write_file"}],
        })
        assert result.passed is False
        assert "research" in result.message.lower()
