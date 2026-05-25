import json

import pytest

from metis.evidence.ledger import EvidenceLedger
from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_records_extracted_command_evidence(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    ledger = EvidenceLedger(state)
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    final = json.dumps(
        {"status": "done", "summary": "已测试全部功能", "evidence_refs": [], "artifact_refs": [], "next_action": ""},
        ensure_ascii=False,
    )
    provider = FakeProvider(
        [
            {
                "tool_calls": [
                    {
                        "name": "run_shell",
                        "arguments": {"command": "python -c \"print('pytest 3 passed')\"", "timeout": 30},
                        "id": "t1",
                    }
                ]
            },
            {"content": final},
        ]
    )
    loop = AgentLoop(provider=provider, registry=registry, state=state, evidence_ledger=ledger, workspace=str(tmp_path))

    result = await loop.run(
        AgentRunRequest(
            session_id="s1",
            messages=[{"role": "user", "content": "run tests"}],
            allowed_tools=["run_shell"],
            max_turns=3,
        )
    )
    evidence = ledger.list_evidence("s1")

    assert result.status == "final"
    assert evidence[0].source_type == "test"
    assert "pytest" in evidence[0].source_ref
    tool_message = json.loads(result.messages[2]["content"])
    assert tool_message["evidence_refs"] == [evidence[0].id]
    assert tool_message["evidence_instruction"]


@pytest.mark.asyncio
async def test_agent_loop_returns_write_file_evidence_refs_to_model(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    ledger = EvidenceLedger(state)
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    final = json.dumps(
        {"status": "blocked", "summary": "wait for evidence", "evidence_refs": [], "artifact_refs": [], "next_action": ""},
        ensure_ascii=False,
    )
    provider = FakeProvider(
        [
            {
                "tool_calls": [
                    {
                        "name": "write_file",
                        "arguments": {"path": "outputs/verified-write.md", "content": "Metis harness note."},
                        "id": "w1",
                    }
                ]
            },
            {"content": final},
        ]
    )
    loop = AgentLoop(provider=provider, registry=registry, state=state, evidence_ledger=ledger, workspace=str(tmp_path))

    result = await loop.run(
        AgentRunRequest(
            session_id="s-write",
            messages=[{"role": "user", "content": "write report"}],
            allowed_tools=["write_file"],
            max_turns=3,
        )
    )
    evidence = ledger.list_evidence("s-write")
    tool_message = json.loads(result.messages[2]["content"])

    assert result.tool_results[0].status == "ok"
    assert evidence[0].source_type == "tool_output"
    assert evidence[0].source_ref.endswith("outputs\\verified-write.md") or evidence[0].source_ref.endswith("outputs/verified-write.md")
    assert tool_message["evidence_refs"] == [evidence[0].id]
