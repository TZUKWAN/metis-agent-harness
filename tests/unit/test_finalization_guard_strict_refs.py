from metis.runtime.finalization import FinalizationGuard
from metis.runtime.strict_output import StrictOutput
from metis.evidence.resolver import EvidenceResolution


def test_finalization_guard_blocks_missing_strict_evidence_ref():
    result = FinalizationGuard().validate(
        final_text="All tests passed.",
        evidence=[],
        tool_results=[{"tool_name": "run_shell", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
        strict_output=StrictOutput(
            status="done",
            summary="All tests passed.",
            evidence_refs=["missing-evidence"],
            artifact_refs=[],
            next_action="",
        ),
    )

    assert result.passed is False
    assert result.status == "blocked"
    assert "missing-evidence" in result.errors[0]


def test_finalization_guard_allows_existing_strict_refs():
    result = FinalizationGuard().validate(
        final_text="All tests passed.",
        evidence=[{"id": "e1", "claim": "Test command executed", "metadata": {"exit_code": 0, "status": "ok"}}],
        artifacts=[{"id": "a1", "path": "report.md"}],
        tool_results=[{"tool_name": "run_shell", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
        strict_output=StrictOutput(
            status="done",
            summary="All tests passed.",
            evidence_refs=["e1"],
            artifact_refs=["a1"],
            next_action="",
        ),
    )

    assert result.passed is True
    assert result.status == "final"


class RejectingResolver:
    def resolve(self, evidence):
        return EvidenceResolution(False, "source_ref does not resolve")


class AcceptingResolver:
    def resolve(self, evidence):
        return EvidenceResolution(True, "ok")


def test_finalization_guard_blocks_unresolved_existing_evidence_ref():
    result = FinalizationGuard(evidence_resolver=RejectingResolver()).validate(
        final_text="All tests passed.",
        evidence=[{"id": "e1", "claim": "Test command executed", "metadata": {"exit_code": 0, "status": "ok"}}],
        tool_results=[{"tool_name": "run_test", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
        strict_output=StrictOutput(
            status="done",
            summary="All tests passed.",
            evidence_refs=["e1"],
            artifact_refs=[],
            next_action="",
        ),
    )

    assert result.passed is False
    assert result.status == "blocked"
    assert "Unresolved evidence ref e1" in result.errors[0]


def test_finalization_guard_allows_resolved_existing_evidence_ref():
    result = FinalizationGuard(evidence_resolver=AcceptingResolver()).validate(
        final_text="All tests passed.",
        evidence=[{"id": "e1", "claim": "Test command executed", "metadata": {"exit_code": 0, "status": "ok"}}],
        tool_results=[{"tool_name": "run_test", "content": "pytest 3 passed", "metadata": {"exit_code": 0}}],
        strict_output=StrictOutput(
            status="done",
            summary="All tests passed.",
            evidence_refs=["e1"],
            artifact_refs=[],
            next_action="",
        ),
    )

    assert result.passed is True
    assert result.verified is True


def test_finalization_guard_strict_done_requires_evidence_ref():
    result = FinalizationGuard(require_done_evidence_refs=True).validate(
        final_text='{"status":"done","summary":"ok","evidence_refs":[],"artifact_refs":[],"next_action":""}',
        strict_output=StrictOutput(
            status="done",
            summary="ok",
            evidence_refs=[],
            artifact_refs=[],
            next_action="",
        ),
    )

    assert result.passed is False
    assert result.status == "blocked"
    assert "requires at least one evidence ref" in result.errors[0]


def test_finalization_guard_strict_blocked_does_not_require_evidence_ref():
    result = FinalizationGuard(require_done_evidence_refs=True).validate(
        final_text='{"status":"blocked","summary":"missing input","evidence_refs":[],"artifact_refs":[],"next_action":"ask"}',
        strict_output=StrictOutput(
            status="blocked",
            summary="missing input",
            evidence_refs=[],
            artifact_refs=[],
            next_action="ask",
        ),
    )

    assert result.passed is True
    assert result.verified is False
