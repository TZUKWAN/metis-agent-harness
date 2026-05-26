import json

import pytest

from metis.evidence.ledger import EvidenceLedger
from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_finalization_guard_blocks_unsupported_completion_claim():
    content = json.dumps(
        {
            "status": "done",
            "summary": "All features have been tested",
            "evidence_refs": [],
            "artifact_refs": [],
            "next_action": "",
        },
        ensure_ascii=False,
    )
    loop = AgentLoop(provider=FakeProvider([{"content": content}]), registry=ToolRegistry(), profile="small")

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "finish"}], max_turns=1))

    assert result.status == "blocked"
    assert any("tested" in error for error in result.errors)
