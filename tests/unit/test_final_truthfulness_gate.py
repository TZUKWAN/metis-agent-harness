from metis.quality.runner import QualityGateRunner


def test_final_truthfulness_gate_blocks_completion_claim_without_evidence():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {"final_text": "已生成并已测试全部功能", "artifacts": [], "evidence": [], "tool_results": []},
    )

    assert result.passed is False
    assert "without evidence" in result.failed_results[0].message


def test_final_truthfulness_gate_allows_plain_summary_without_claim():
    result = QualityGateRunner().run(["no_fake_completion"], {"final_text": "下一步需要运行测试"})

    assert result.passed is True


def test_final_truthfulness_gate_rejects_test_claim_with_only_read_tool():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {
            "final_text": "已测试全部功能",
            "tool_results": [{"tool_name": "read_file", "content": "source"}],
            "artifacts": [],
            "evidence": [],
        },
    )

    assert result.passed is False
    assert "已测试" in result.failed_results[0].message


def test_final_truthfulness_gate_accepts_test_claim_with_pytest_command():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {
            "final_text": "已测试全部功能",
            "tool_results": [{"tool_name": "run_shell", "content": "pytest: 10 passed"}],
            "artifacts": [],
            "evidence": [],
        },
    )

    assert result.passed is True


def test_final_truthfulness_gate_blocks_api_claim_without_api_evidence():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {"final_text": "The API was called successfully.", "artifacts": [], "evidence": [], "tool_results": []},
    )

    assert result.passed is False
    assert "called_api" in result.failed_results[0].metadata["missing_claims"]
    assert result.failed_results[0].metadata["claim_verifications"][0]["required_evidence"]


def test_final_truthfulness_gate_accepts_api_claim_with_http_evidence():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {
            "final_text": "The API was called successfully.",
            "artifacts": [],
            "evidence": [],
            "tool_results": [
                {
                    "tool_name": "run_shell",
                    "content": "curl https://example.test/api returned HTTP 200",
                    "metadata": {"exit_code": 0},
                }
            ],
        },
    )

    assert result.passed is True
    assert result.results[0].metadata["claim_verifications"][0]["claim"] == "called_api"


def test_final_truthfulness_gate_blocks_release_claim_without_release_evidence():
    result = QualityGateRunner().run(
        ["no_fake_completion"],
        {"final_text": "The release is complete.", "artifacts": [], "evidence": [], "tool_results": []},
    )

    assert result.passed is False
    assert "released" in result.failed_results[0].metadata["missing_claims"]
