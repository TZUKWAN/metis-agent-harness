from metis.runtime.finalization import FinalizationGuard


def test_finalization_guard_blocks_fake_test_claim():
    result = FinalizationGuard().validate(final_text="All features have been tested", tool_results=[])

    assert result.passed is False
    assert result.status == "blocked"


def test_finalization_guard_allows_supported_test_claim():
    result = FinalizationGuard().validate(
        final_text="All features have been tested",
        tool_results=[{"tool_name": "run_shell", "content": "pytest: 3 passed"}],
    )

    assert result.passed is True
    assert result.status == "final"


def test_finalization_guard_exposes_claim_verification_table():
    result = FinalizationGuard().validate(final_text="The release is complete.", tool_results=[])

    assert result.passed is False
    assert result.claim_verifications
    assert result.claim_verifications[0]["claim"] == "released"
    assert result.claim_verifications[0]["verified"] is False
