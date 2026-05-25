from metis.swarm.synthesizer import ResultSynthesizer


def test_result_synthesizer_excludes_failed_or_audit_failed_results():
    result = ResultSynthesizer().synthesize(
        [
            {"summary": "ok", "audit_passed": True, "evidence_refs": ["e1"], "artifact_refs": ["a1"]},
            {"summary": "bad", "audit_passed": False, "evidence_refs": ["e2"], "artifact_refs": ["a2"]},
            {"summary": "failed", "status": "failed"},
        ]
    )

    assert result["status"] == "done"
    assert result["summary"] == "ok"
    assert result["evidence_refs"] == ["e1"]
