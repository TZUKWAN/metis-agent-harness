import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolPermissionLevel, ToolSpec


@pytest.mark.asyncio
async def test_agent_loop_enforces_allowed_tool_permissions():
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {}, "id": "w1"}]},
            {
                "content": '{"status":"needs_more_work","summary":"permission blocked","evidence_refs":[],"artifact_refs":[],"next_action":"ask for permission"}'
            },
        ]
    )
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {"type": "object"},
            lambda args, ctx: {"ok": True},
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    loop = AgentLoop(provider=provider, registry=registry, profile="small")

    result = await loop.run(
        AgentRunRequest(
            messages=[{"role": "user", "content": "write"}],
            max_turns=2,
            allowed_tool_permissions=[ToolPermissionLevel.READ_ONLY.value],
        )
    )

    assert result.tool_results[0].status == "blocked"
    assert "permission not allowed" in result.tool_results[0].error
