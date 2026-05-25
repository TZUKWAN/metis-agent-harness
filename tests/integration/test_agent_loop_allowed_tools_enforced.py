import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_agent_loop_blocks_model_calling_unallowed_registered_tool():
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {"path": "x"}, "id": "w1"}]},
            {
                "content": '{"status":"done","summary":"blocked unsafe call","evidence_refs":[],"artifact_refs":[],"next_action":""}'
            },
        ]
    )
    registry = ToolRegistry()
    registry.register(ToolSpec("read_file", "Read", {"type": "object"}, lambda args, ctx: {"ok": True}))
    registry.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=provider, registry=registry, profile="small")

    result = await loop.run(
        AgentRunRequest(
            messages=[{"role": "user", "content": "read only"}],
            allowed_tools=["read_file"],
            max_turns=2,
        )
    )

    assert result.tool_results[0].status == "blocked"
    assert "not allowed" in result.tool_results[0].error
