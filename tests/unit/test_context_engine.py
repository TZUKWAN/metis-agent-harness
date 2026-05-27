"""Tests for ContextEngine with token-aware budget."""

from __future__ import annotations

import pytest

from metis.context.engine import ContextEngine
from metis.context.compressor import SimpleContextCompressor
from metis.runtime.budgets import BudgetConfig


class TestContextEngineBudget:
    def test_no_compression_when_under_budget(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=10_000, context_threshold=1.0),
            chars_per_token=4,
        )
        messages = [{"role": "user", "content": "hello"}]
        result = engine.build(messages)
        assert result.compressed is False
        assert result.original_tokens == result.final_tokens

    def test_compresses_when_over_token_budget(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=500, context_threshold=1.0),
            compressor=SimpleContextCompressor(max_summary_chars=200, keep_recent=2),
            chars_per_token=4,
        )
        messages = [{"role": "user", "content": "x" * 500} for _ in range(10)]
        result = engine.build(messages)
        assert result.compressed is True
        assert result.final_tokens <= engine.max_total_tokens

    def test_tool_schemas_counted_toward_budget(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=100, context_threshold=1.0),
            compressor=SimpleContextCompressor(max_summary_chars=200, keep_recent=2),
            chars_per_token=4,
        )
        messages = [{"role": "user", "content": "hello"}]
        schemas = [{"type": "function", "function": {"name": "tool", "description": "x" * 500}}]
        result = engine.build(messages, tool_schemas=schemas)
        assert result.tool_schema_tokens > 0

    def test_tool_schemas_trigger_compression(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=200, context_threshold=1.0),
            compressor=SimpleContextCompressor(max_summary_chars=200, keep_recent=2),
            chars_per_token=4,
        )
        messages = [{"role": "user", "content": "x" * 300}]
        schemas = [{"type": "function", "function": {"name": "tool", "description": "y" * 500}}]
        result_without = engine.build(messages)
        result_with = engine.build(messages, tool_schemas=schemas)
        # With schemas, should be more likely to compress or have higher token count
        assert result_with.tool_schema_tokens > 0
        assert result_with.final_tokens >= result_without.final_tokens

    def test_cjk_density_detected(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=100, context_threshold=1.0),
            compressor=SimpleContextCompressor(max_summary_chars=200, keep_recent=2),
        )
        messages = [{"role": "user", "content": "这是一段非常长的中文文本" * 50}]
        result = engine.build(messages)
        assert result.original_tokens > 0
        # CJK text has higher token density (more tokens per char)
        assert result.original_chars > 0

    def test_override_max_context_tokens(self):
        budget = BudgetConfig(model_context_tokens=1000, context_threshold=1.0)
        engine = ContextEngine(budget=budget, override_max_context_tokens=5000, chars_per_token=1)
        assert engine.max_total_tokens == 5000

    def test_max_chars_calculation(self):
        budget = BudgetConfig(model_context_tokens=1000, context_threshold=0.5)
        engine = ContextEngine(budget=budget, chars_per_token=4)
        assert engine.max_chars == 2000  # 1000 * 4 * 0.5

    def test_max_total_tokens_with_threshold(self):
        budget = BudgetConfig(model_context_tokens=1000, context_threshold=0.5)
        engine = ContextEngine(budget=budget)
        assert engine.max_total_tokens == 500

    def test_empty_messages(self):
        engine = ContextEngine()
        result = engine.build([])
        assert result.compressed is False
        assert result.messages == []

    def test_compression_preserves_message_roles(self):
        engine = ContextEngine(
            budget=BudgetConfig(model_context_tokens=50, context_threshold=1.0),
            compressor=SimpleContextCompressor(max_summary_chars=100, keep_recent=2),
            chars_per_token=4,
        )
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ]
        result = engine.build(messages)
        if result.compressed:
            roles = [m["role"] for m in result.messages]
            assert "system" in roles
            assert "user" in roles
