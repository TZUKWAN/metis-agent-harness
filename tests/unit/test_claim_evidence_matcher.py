from metis.evidence.matcher import ClaimEvidenceMatcher


def test_claim_evidence_matcher_requires_successful_test_evidence():
    matcher = ClaimEvidenceMatcher()

    failed = matcher.match(
        final_text="All features have been tested",
        tool_results=[{"tool_name": "run_shell", "content": "pytest failed", "metadata": {"exit_code": 1}}],
    )
    passed = matcher.match(
        final_text="All features have been tested",
        tool_results=[{"tool_name": "run_shell", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
    )

    assert failed.passed is False
    assert failed.missing_claims == ["tested"]
    assert passed.passed is True


def test_claim_evidence_matcher_requires_upload_evidence():
    matcher = ClaimEvidenceMatcher()

    result = matcher.match(final_text="Files have been uploaded to repository", tool_results=[{"tool_name": "read_file", "content": "ok"}])

    assert result.passed is False
    assert result.missing_claims == ["uploaded"]
