import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_agent_loop_records_messages_and_tool_calls(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    provider = FakeProvider(
            [
                {"tool_calls": [{"name": "echo", "arguments": {"value": "tracked"}, "id": "call-tracked"}]},
                {"content": '{"status":"done","summary":"done","evidence_refs":[],"artifact_refs":[],"next_action":""}'},
            ]
        )
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"echo": args["value"]}))
    loop = AgentLoop(provider=provider, registry=registry, state=store)

    result = await loop.run(
        AgentRunRequest(
            session_id="session-tracked",
            messages=[{"role": "user", "content": "run tracked"}],
            max_turns=3,
        )
    )

    messages = store.list_messages("session-tracked")
    calls = store.list_tool_calls("session-tracked")

    assert result.status == "final"
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert calls[0]["id"] == "call-tracked"
    assert calls[0]["tool_name"] == "echo"
    assert calls[0]["status"] == "ok"
