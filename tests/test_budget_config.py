"""Tests for BudgetConfig profile presets."""

from metis.runtime.budgets import BudgetConfig


def test_default_profile_has_sensible_defaults():
    cfg = BudgetConfig.for_profile("default")
    assert cfg.per_tool_chars == 8000
    assert cfg.per_turn_chars == 30000
    assert cfg.model_context_tokens == 32768


def test_small_profile_optimized_for_8b():
    cfg = BudgetConfig.for_profile("small")
    assert cfg.model_context_tokens == 128000
    assert cfg.per_tool_chars == 4000
    assert cfg.per_turn_chars == 20000
    assert cfg.preview_chars == 1200
    assert cfg.context_threshold == 0.50


def test_small_profile_tighter_than_default():
    small = BudgetConfig.for_profile("small")
    default = BudgetConfig.for_profile("default")
    assert small.per_tool_chars < default.per_tool_chars
    assert small.per_turn_chars < default.per_turn_chars
    assert small.preview_chars < default.preview_chars


def test_deep_profile_has_largest_budgets():
    cfg = BudgetConfig.for_profile("deep")
    assert cfg.per_tool_chars == 24000
    assert cfg.per_turn_chars == 120000
    assert cfg.model_context_tokens == 128000
    assert cfg.context_threshold == 0.75


def test_unknown_profile_returns_default():
    cfg = BudgetConfig.for_profile("unknown")
    default = BudgetConfig()
    assert cfg == default


def test_frozen_dataclass():
    cfg = BudgetConfig.for_profile("small")
    raised = False
    try:
        cfg.per_tool_chars = 99999
    except AttributeError:
        raised = True
    assert raised
