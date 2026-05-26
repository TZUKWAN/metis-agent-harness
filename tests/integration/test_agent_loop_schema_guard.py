import json

import pytest

from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_agent_loop_blocks_schema_invalid_tool_call_without_handler_side_effect():
    called = False

    def handler(args, ctx):
        nonlocal called
        called = True
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            handler,
        )
    )
    final = json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "x"}, "id": "c1"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="balanced").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["write_file"], max_turns=2)
    )

    assert called is False
    assert result.tool_results[0].status == "blocked"
    assert result.tool_results[0].metadata["schema_valid"] is False
    assert result.status == "final"


@pytest.mark.asyncio
async def test_agent_loop_returns_repairable_schema_feedback_then_accepts_corrected_call():
    writes = []

    def handler(args, ctx):
        writes.append(args)
        return {"ok": True, "path": args["path"]}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            handler,
        )
    )
    final = json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "x"}, "id": "c1"}]},
            {"tool_calls": [{"name": "write_file", "arguments": {"path": "out.txt", "content": "x"}, "id": "c2"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="balanced").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["write_file"], max_turns=3)
    )

    assert writes == [{"path": "out.txt", "content": "x"}]
    assert result.tool_results[0].status == "blocked"
    assert result.tool_results[1].status == "ok"
    schema_feedback = json.loads(result.messages[2]["content"])
    assert schema_feedback["error_type"] == "schema_validation_failed"
    assert schema_feedback["tool"] == "write_file"
    assert schema_feedback["recoverable"] is True
    assert schema_feedback["retry_allowed"] is True
    assert "path" in " ".join(schema_feedback["schema_errors"])
    assert "Add the required argument $.path." in schema_feedback["schema_repair_hints"]
    assert "Retry the same tool" in schema_feedback["repair_instruction"]
    hint_events = [event for event in result.trace_events if event["event_type"] == "schema.repair_hint"]
    assert len(hint_events) == 1
    assert hint_events[0]["tool_name"] == "write_file"
    assert hint_events[0]["tool_call_id"] == "c1"
    assert hint_events[0]["attributes"]["schema_repair_hints"] == ["Add the required argument $.path."]
    assert hint_events[0]["attributes"]["schema_repair_hint_types"] == ["add_required_property"]
    assert hint_events[0]["attributes"]["parent_event_id"]
    assert result.status == "final"


@pytest.mark.asyncio
async def test_agent_loop_repairs_extra_argument_after_schema_feedback():
    calls = []

    def handler(args, ctx):
        calls.append(args)
        return {"ok": True, "path": args["path"]}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "read_file",
            "Read",
            {
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1}},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler,
        )
    )
    final = json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "read_file", "arguments": {"path": "README.md", "url": "https://example.com"}, "id": "c1"}]},
            {"tool_calls": [{"name": "read_file", "arguments": {"path": "README.md"}, "id": "c2"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="balanced").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["read_file"], max_turns=3)
    )

    assert calls == [{"path": "README.md"}]
    assert result.tool_results[0].status == "blocked"
    assert result.tool_results[0].metadata["schema_errors"] == ["$.url: additional property not allowed"]
    assert result.tool_results[1].status == "ok"
    feedback = json.loads(result.messages[2]["content"])
    assert feedback["error_type"] == "schema_validation_failed"
    assert feedback["schema_repair_hints"] == ["Remove the unsupported argument at $.url."]
    assert feedback["schema_repair_hint_types"] == ["remove_additional_property"]
    assert feedback["schema_repair_hint_details"][0]["hint_type"] == "remove_additional_property"
    assert feedback["schema_repair_hint_details"][0]["schema_path"] == "$.url"
    hint_events = [event for event in result.trace_events if event["event_type"] == "schema.repair_hint"]
    assert len(hint_events) == 1
    assert hint_events[0]["summary"] == "schema_repair_hint_types=remove_additional_property"
    assert hint_events[0]["attributes"]["schema_repair_hint_details"][0]["schema_path"] == "$.url"
    assert result.status == "final"


@pytest.mark.asyncio
async def test_agent_loop_repairs_empty_command_array_after_schema_feedback():
    calls = []

    def handler(args, ctx):
        calls.append(args)
        return {"ok": True, "command": args["command"]}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_command",
            "Run command",
            {
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                        ]
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler,
        )
    )
    final = json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "run_command", "arguments": {"command": []}, "id": "c1"}]},
            {"tool_calls": [{"name": "run_command", "arguments": {"command": ["python", "--version"]}, "id": "c2"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="balanced").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["run_command"], max_turns=3)
    )

    assert calls == [{"command": ["python", "--version"]}]
    assert result.tool_results[0].status == "blocked"
    assert result.tool_results[1].status == "ok"
    feedback = json.loads(result.messages[2]["content"])
    assert feedback["error_type"] == "schema_validation_failed"
    assert any("minItems 1" in error for error in feedback["schema_errors"])
    assert any("do not pass an empty array" in hint for hint in feedback["schema_repair_hints"])
    assert "increase_array_items" in feedback["schema_repair_hint_types"]
    assert result.status == "final"


@pytest.mark.asyncio
async def test_agent_loop_returns_structured_runtime_error_feedback():
    def handler(args, ctx):
        raise RuntimeError("missing prerequisite")

    registry = ToolRegistry()
    registry.register(ToolSpec("fragile_tool", "Fragile", {"type": "object"}, handler))
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "fragile_tool", "arguments": {}, "id": "c1"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="balanced").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["fragile_tool"], max_turns=2)
    )

    feedback = json.loads(result.messages[2]["content"])
    assert feedback["error_type"] == "runtime_error"
    assert feedback["tool"] == "fragile_tool"
    assert feedback["recoverable"] is True
    assert feedback["retry_allowed"] is True
    assert "missing prerequisite" in feedback["error"]


@pytest.mark.asyncio
async def test_agent_loop_marks_retry_budget_exhausted_for_repeated_recoverable_failure():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "x"}, "id": "c1"}]},
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "x"}, "id": "c2"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="small").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["write_file"], max_turns=3)
    )

    first_feedback = json.loads(result.messages[2]["content"])
    second_feedback = json.loads(result.messages[4]["content"])
    assert first_feedback["retry_allowed"] is True
    assert second_feedback["retry_allowed"] is False
    assert result.tool_results[1].metadata["retry_budget_exhausted"] is True
    assert result.tool_results[1].metadata["repair_attempt_number"] == 2
    assert "Retry budget exhausted" in second_feedback["repair_instruction"]


@pytest.mark.asyncio
async def test_agent_loop_pre_dispatch_blocks_repeated_call_after_retry_budget_exhausted():
    calls = 0

    def handler(args, ctx):
        nonlocal calls
        calls += 1
        raise RuntimeError("missing prerequisite")

    registry = ToolRegistry()
    registry.register(ToolSpec("fragile_tool", "Fragile", {"type": "object"}, handler))
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "fragile_tool", "arguments": {"mode": "same"}, "id": "c1"}]},
            {"tool_calls": [{"name": "fragile_tool", "arguments": {"mode": "same"}, "id": "c2"}]},
            {"tool_calls": [{"name": "fragile_tool", "arguments": {"mode": "same"}, "id": "c3"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="small").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["fragile_tool"], max_turns=4)
    )

    # Loop detection triggers on 3rd repeated tool call pattern before retry budget pre-dispatch block
    assert calls == 2
    assert result.tool_results[0].metadata["failure_type"] == "runtime_error"
    assert result.tool_results[1].metadata["retry_budget_exhausted"] is True
    assert result.status == "blocked"
    assert any("loop detected" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_agent_loop_pre_dispatch_blocks_schema_failure_shape_after_budget_exhausted():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "first"}, "id": "c1"}]},
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "second"}, "id": "c2"}]},
            {"tool_calls": [{"name": "write_file", "arguments": {"content": "third"}, "id": "c3"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="small").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["write_file"], max_turns=4)
    )

    assert result.tool_results[0].metadata["failure_type"] == "schema_validation_failed"
    assert result.tool_results[1].metadata["retry_budget_exhausted"] is True
    assert result.tool_results[2].metadata["failure_type"] == "retry_budget_exhausted"
    assert result.tool_results[2].metadata["original_failure_type"] == "schema_validation_failed"
    assert result.tool_results[2].metadata["failure_shape_key"] == "$.path: missing required property"


@pytest.mark.asyncio
async def test_agent_loop_pre_dispatch_blocks_command_semantic_shape_after_budget_exhausted():
    calls = 0

    def handler(args, ctx):
        nonlocal calls
        calls += 1
        return {"exit_code": 1, "stderr": "failed"}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_test",
            "Run tests",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            handler,
        )
    )
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/a.py"}, "id": "c1"}]},
            {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/b.py"}, "id": "c2"}]},
            {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/c.py"}, "id": "c3"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="small").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["run_test"], max_turns=4)
    )

    assert calls == 2
    assert result.tool_results[0].metadata["failure_type"] == "command_failed"
    assert result.tool_results[1].metadata["retry_budget_exhausted"] is True
    assert result.tool_results[1].metadata["failure_shape_key"] == "python pytest"
    assert result.tool_results[2].metadata["failure_type"] == "retry_budget_exhausted"
    assert result.tool_results[2].metadata["original_failure_type"] == "command_failed"
    assert result.tool_results[2].metadata["failure_shape_key"] == "python pytest"


@pytest.mark.asyncio
async def test_agent_loop_records_runtime_error_shape_for_lightly_changed_arguments():
    def handler(args, ctx):
        raise RuntimeError(f"missing prerequisite {args['mode']}")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "fragile_tool",
            "Fragile",
            {"type": "object", "properties": {"mode": {"type": "string"}}, "required": ["mode"]},
            handler,
        )
    )
    final = json.dumps({"status": "blocked", "summary": "blocked", "evidence_refs": [], "artifact_refs": [], "next_action": ""})
    provider = FakeProvider(
        [
            {"tool_calls": [{"name": "fragile_tool", "arguments": {"mode": "1"}, "id": "c1"}]},
            {"tool_calls": [{"name": "fragile_tool", "arguments": {"mode": "2"}, "id": "c2"}]},
            {"content": final},
        ]
    )

    result = await AgentLoop(provider=provider, registry=registry, profile="small").run(
        AgentRunRequest(messages=[{"role": "user", "content": "run"}], allowed_tools=["fragile_tool"], max_turns=3)
    )

    assert result.tool_results[0].metadata["failure_shape_key"] == "RuntimeError:runtimeerror: missing prerequisite <value>"
    assert result.tool_results[1].metadata["failure_shape_key"] == "RuntimeError:runtimeerror: missing prerequisite <value>"
    assert result.tool_results[1].metadata["retry_budget_exhausted"] is True
