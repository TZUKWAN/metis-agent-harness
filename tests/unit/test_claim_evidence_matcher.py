from metis.evidence.matcher import ClaimEvidenceMatcher


def test_claim_evidence_matcher_requires_successful_test_evidence():
    matcher = ClaimEvidenceMatcher()

    failed = matcher.match(
        final_text="已测试全部功能",
        tool_results=[{"tool_name": "run_shell", "content": "pytest failed", "metadata": {"exit_code": 1}}],
    )
    passed = matcher.match(
        final_text="已测试全部功能",
        tool_results=[{"tool_name": "run_shell", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
    )

    assert failed.passed is False
    assert failed.missing_claims == ["已测试"]
    assert passed.passed is True


def test_claim_evidence_matcher_requires_upload_evidence():
    matcher = ClaimEvidenceMatcher()

    result = matcher.match(final_text="已上传到仓库", tool_results=[{"tool_name": "read_file", "content": "ok"}])

    assert result.passed is False
    assert result.missing_claims == ["已上传"]
