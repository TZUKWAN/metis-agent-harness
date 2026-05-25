from metis.evidence.ledger import EvidenceLedger
from metis.state.sqlite_store import SQLiteStateStore


def test_evidence_ledger_records_and_queries_claims(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    ledger = EvidenceLedger(state)

    record = ledger.record_claim(
        session_id=session_id,
        claim="pytest passed",
        source_type="command",
        source_ref="python -m pytest -q",
    )

    assert ledger.list_evidence(session_id) == [record]
    assert ledger.find_by_source(session_id, "command") == [record]
    assert "pytest passed" in ledger.summarize_for_prompt(session_id)
