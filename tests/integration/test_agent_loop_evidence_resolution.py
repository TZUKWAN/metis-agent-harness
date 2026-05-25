import json

import pytest

from metis.evidence.ledger import EvidenceLedger
from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_blocks_existing_but_unresolved_evidence_ref(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("s1")
    ledger = EvidenceLedger(state)
    ledger.record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 0, "status": "ok"},
        evidence_id="e1",
    )
    content = json.dumps(
        {
            "status": "done",
            "summary": "All tests passed.",
            "evidence_refs": ["e1"],
            "artifact_refs": [],
            "next_action": "",
        },
        ensure_ascii=False,
    )
    loop = AgentLoop(
        provider=FakeProvider([{"content": content}]),
        registry=ToolRegistry(),
        profile="small",
        state=state,
        evidence_ledger=ledger,
    )

    result = await loop.run(
        AgentRunRequest(session_id=session_id, messages=[{"role": "user", "content": "finish"}], max_turns=1)
    )

    assert result.status == "blocked"
    assert any("Unresolved evidence ref e1" in error for error in result.errors)
