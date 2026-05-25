from metis.runtime.budgets import BudgetConfig


def test_budget_profiles_are_distinct():
    small = BudgetConfig.for_profile("small")
    default = BudgetConfig.for_profile("default")
    deep = BudgetConfig.for_profile("deep")

    assert small.per_tool_chars < default.per_tool_chars < deep.per_tool_chars
    assert small.context_threshold < deep.context_threshold
