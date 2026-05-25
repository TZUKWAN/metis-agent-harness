import json

import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_maps_strict_blocked_status():
    content = json.dumps(
        {"status": "blocked", "summary": "blocked by missing input", "evidence_refs": [], "artifact_refs": [], "next_action": "ask user"}
    )
    loop = AgentLoop(provider=FakeProvider([{"content": content}]), registry=ToolRegistry(), profile="small")

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "run"}], max_turns=1))

    assert result.status == "blocked"


@pytest.mark.asyncio
async def test_agent_loop_maps_strict_needs_more_work_status():
    content = json.dumps(
        {
            "status": "needs_more_work",
            "summary": "need one more tool call",
            "evidence_refs": [],
            "artifact_refs": [],
            "next_action": "continue",
        }
    )
    loop = AgentLoop(provider=FakeProvider([{"content": content}]), registry=ToolRegistry(), profile="small")

    result = await loop.run(AgentRunRequest(messages=[{"role": "user", "content": "run"}], max_turns=1))

    assert result.status == "needs_more_work"
