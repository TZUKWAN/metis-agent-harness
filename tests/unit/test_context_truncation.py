"""Tests for automatic context truncation on length errors."""

from __future__ import annotations

import pytest

from metis.runtime.loop import AgentLoop


class TestTruncateForContext:
    def test_keeps_system_messages(self):
        messages = [
            {"role": "system", "content": "sys1"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ]
        result = AgentLoop._truncate_for_context(messages)
        assert any(m.get("role") == "system" for m in result)

    def test_truncates_oldest(self):
        messages = [
            {"role": "user", "content": f"u{i}"}
            for i in range(20)
        ]
        result = AgentLoop._truncate_for_context(messages)
        assert len(result) < len(messages)
        assert result[-1]["content"] == "u19"

    def test_keeps_at_least_4(self):
        messages = [
            {"role": "user", "content": f"u{i}"}
            for i in range(6)
        ]
        result = AgentLoop._truncate_for_context(messages)
        assert len(result) >= 4

    def test_empty_input(self):
        result = AgentLoop._truncate_for_context([])
        assert result == []

    def test_only_system(self):
        messages = [
            {"role": "system", "content": "sys"},
        ]
        result = AgentLoop._truncate_for_context(messages)
        assert len(result) == 1

    def test_preserves_recent_proportion(self):
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(100)]
        result = AgentLoop._truncate_for_context(messages)
        non_system = [m for m in result if m.get("role") != "system"]
        # Keeps at least half of non-system messages
        assert len(non_system) >= 50
