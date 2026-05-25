from metis.evidence.matcher import ClaimEvidenceMatcher


def test_claim_evidence_matcher_detects_english_test_claims():
    matcher = ClaimEvidenceMatcher()

    failed = matcher.match(
        final_text="All tests passed.",
        tool_results=[{"tool_name": "run_shell", "content": "pytest failed", "metadata": {"exit_code": 1}}],
    )
    passed = matcher.match(
        final_text="All tests passed.",
        tool_results=[{"tool_name": "run_shell", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
    )

    assert failed.passed is False
    assert passed.passed is True


def test_claim_evidence_matcher_ignores_failed_write_for_generated_claim():
    matcher = ClaimEvidenceMatcher()

    result = matcher.match(
        final_text="Report generated.",
        tool_results=[{"tool_name": "write_file", "content": "permission denied", "status": "error"}],
    )

    assert result.passed is False


def test_claim_evidence_matcher_requires_successful_push_for_english_upload_claim():
    matcher = ClaimEvidenceMatcher()

    result = matcher.match(
        final_text="Uploaded to GitHub.",
        tool_results=[{"tool_name": "run_shell", "content": "git push failed", "metadata": {"exit_code": 1}}],
    )

    assert result.passed is False
