from metis.swarm.auditor import Auditor


def test_swarm_auditor_blocks_completion_claim_without_artifact():
    report = Auditor().audit(final_text="The report has been generated", artifacts=[], evidence=[], tool_results=[])

    assert report.passed is False
    assert any("No artifacts" in message or "without evidence" in message for message in report.messages)
