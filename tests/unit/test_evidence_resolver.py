from metis.artifacts.store import ArtifactStore
from metis.evidence.ledger import EvidenceLedger
from metis.evidence.resolver import EvidenceResolver
from metis.state.sqlite_store import SQLiteStateStore


def test_evidence_resolver_resolves_artifact_source_ref(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    artifact_store = ArtifactStore(state)
    ledger = EvidenceLedger(state)
    session_id = state.create_session("s1")
    artifact_path = tmp_path / "report.md"
    artifact_path.write_text("# Report\n", encoding="utf-8")
    artifact = artifact_store.register_artifact(session_id=session_id, path=artifact_path, artifact_type="markdown")
    evidence = ledger.record_claim(
        session_id=session_id,
        claim="Report generated",
        source_type="artifact",
        source_ref=artifact.id,
    )

    result = EvidenceResolver(state=state, artifact_store=artifact_store).resolve(evidence)

    assert result.passed is True


def test_evidence_resolver_rejects_missing_artifact_source_ref(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="Report generated",
        source_type="artifact",
        source_ref="missing",
    )

    result = EvidenceResolver(state=state, artifact_store=ArtifactStore(state)).resolve(evidence)

    assert result.passed is False
    assert "not found" in result.reason


def test_evidence_resolver_resolves_successful_test_command(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    state.record_tool_call(
        session_id,
        "run_test",
        {"command": ["python", "-m", "pytest", "-q"]},
        result='{"command":["python","-m","pytest","-q"],"exit_code":0,"stdout":"1 passed"}',
        status="ok",
        call_id="t1",
    )
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 0, "status": "ok"},
    )

    result = EvidenceResolver(state=state).resolve(evidence)

    assert result.passed is True


def test_evidence_resolver_rejects_failed_test_command(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    state.record_tool_call(
        session_id,
        "run_test",
        {"command": ["python", "-m", "pytest", "-q"]},
        result='{"command":["python","-m","pytest","-q"],"exit_code":1,"stdout":"1 failed"}',
        status="error",
        error="Command failed with exit_code=1",
        call_id="t1",
    )
    evidence = EvidenceLedger(state).record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 1, "status": "error"},
    )

    result = EvidenceResolver(state=state).resolve(evidence)

    assert result.passed is False
