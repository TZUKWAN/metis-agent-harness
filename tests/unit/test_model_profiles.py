from metis.runtime.profiles import get_model_profile


def test_model_profiles_can_be_loaded():
    small = get_model_profile("small")
    balanced = get_model_profile("balanced")
    small_strict = get_model_profile("small_strict")
    deep = get_model_profile("deep")

    assert small.max_tools_per_turn == 8
    assert small.one_tool_call_per_turn is True
    assert balanced.strict_output is True
    assert small_strict.require_done_evidence_refs is True
    assert deep.budget.per_tool_chars > small.budget.per_tool_chars
