"""Tests for ContextEngine dynamic budget override from provider capabilities."""

from __future__ import annotations

from metis.context.engine import ContextEngine
from metis.runtime.budgets import BudgetConfig


def test_override_max_context_tokens_increases_budget():
    budget = BudgetConfig(model_context_tokens=32_768, context_threshold=1.0)
    engine = ContextEngine(budget=budget, chars_per_token=1, override_max_context_tokens=128_000)
    assert engine.max_chars == 128_000


def test_no_override_uses_budget_default():
    budget = BudgetConfig(model_context_tokens=32_768, context_threshold=1.0)
    engine = ContextEngine(budget=budget, chars_per_token=1)
    assert engine.max_chars == 32_768


def test_zero_override_ignored():
    budget = BudgetConfig(model_context_tokens=32_768, context_threshold=1.0)
    engine = ContextEngine(budget=budget, chars_per_token=1, override_max_context_tokens=0)
    assert engine.max_chars == 32_768


def test_override_with_threshold():
    budget = BudgetConfig(model_context_tokens=32_768, context_threshold=0.5)
    engine = ContextEngine(budget=budget, chars_per_token=4, override_max_context_tokens=100_000)
    assert engine.max_chars == 200_000
