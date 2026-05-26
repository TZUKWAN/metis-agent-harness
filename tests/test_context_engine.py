"""Tests for metis/context/engine.py."""

from metis.context.engine import ContextEngine, ContextBuildResult
from metis.runtime.budgets import BudgetConfig


def test_build_no_compression_needed():
    engine = ContextEngine(budget=BudgetConfig(model_context_tokens=1000, context_threshold=0.8))
    msgs = [{"role": "user", "content": "hello"}]
    result = engine.build(msgs)
    assert not result.compressed
    assert result.messages == msgs


def test_build_triggers_compression():
    budget = BudgetConfig(model_context_tokens=100, context_threshold=0.5, per_tool_chars=50)
    engine = ContextEngine(budget=budget, chars_per_token=1)
    msgs = [{"role": "user", "content": "a" * 200}]
    result = engine.build(msgs)
    assert result.compressed
    assert result.final_chars < result.original_chars


def test_max_chars_calculation():
    engine = ContextEngine(budget=BudgetConfig(model_context_tokens=1000, context_threshold=0.5), chars_per_token=4)
    assert engine.max_chars == 2000


def test_empty_messages():
    engine = ContextEngine()
    result = engine.build([])
    assert not result.compressed
    assert result.final_chars == 0


def test_result_is_frozen():
    result = ContextBuildResult(messages=[], compressed=False, original_chars=0, final_chars=0, max_chars=100)
    import pytest
    with pytest.raises(AttributeError):
        result.compressed = True
