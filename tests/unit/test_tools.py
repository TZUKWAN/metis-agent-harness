import json

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.runtime.response import ToolCall
from metis.tools.builtin import register_builtin_tools
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolFilter, ToolRegistry
from metis.tools.spec import ToolContext, ToolPermissionLevel, ToolSpec


def test_register_and_schema():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo args",
            parameters={"type": "object", "properties": {"value": {"type": "string"}}},
            handler=lambda args, ctx: args,
            category="test",
        )
    )

    schemas = registry.schemas(ToolFilter(categories={"test"}))

    assert registry.list_tools() == ["echo"]
    assert schemas[0]["function"]["name"] == "echo"


def test_duplicate_rejected():
    registry = ToolRegistry()
    spec = ToolSpec("x", "x", {"type": "object"}, lambda args, ctx: {})
    registry.register(spec)

    try:
        registry.register(spec)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate registration did not fail")


def test_dispatch_success():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"ok": args["x"]}))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="echo", arguments={"x": 3}, id="call1"), ToolContext())

    assert result.status == "ok"
    assert json.loads(result.content) == {"ok": 3}


def test_dispatch_blocked_by_hook():
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"ok": True}))
    hooks = HookBus()

    def block(ctx):
        ctx["blocked"] = True
        ctx["block_reason"] = "no"
        return ctx

    hooks.register(EventType.TOOL_PRE_DISPATCH, block)
    dispatcher = ToolDispatcher(registry, hooks)

    result = dispatcher.dispatch(ToolCall(name="echo", arguments={}, id="call1"), ToolContext())

    assert result.status == "blocked"
    assert json.loads(result.content) == {"error": "no"}
    assert result.metadata["failure_type"] == "hook_blocked"
    assert result.metadata["recoverable"] is False


def test_dispatch_exception():
    registry = ToolRegistry()

    def bad(args, ctx):
        raise RuntimeError("boom")

    registry.register(ToolSpec("bad", "Bad", {"type": "object"}, bad))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="bad", arguments={}), ToolContext())

    assert result.failed
    assert "boom" in result.content
    assert result.metadata["failure_type"] == "runtime_error"
    assert result.metadata["recoverable"] is True
    assert result.metadata["exception_type"] == "RuntimeError"


def test_dispatch_unknown_tool_returns_repair_metadata():
    dispatcher = ToolDispatcher(ToolRegistry())

    result = dispatcher.dispatch(ToolCall(name="invented_tool", arguments={}, id="call1"), ToolContext())

    assert result.status == "error"
    assert result.metadata["failure_type"] == "unknown_tool"
    assert result.metadata["retry_allowed"] is True
    assert "available tool names" in result.metadata["repair_instruction"]


def test_dispatch_blocks_tool_not_in_allowed_context():
    registry = ToolRegistry()
    registry.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: {"ok": True}))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(
        ToolCall(name="write_file", arguments={}, id="call1"),
        ToolContext(allowed_tools=["read_file"]),
    )

    assert result.status == "blocked"
    assert "not allowed" in result.error
    assert result.metadata["failure_type"] == "tool_not_allowed"
    assert result.metadata["recoverable"] is True


def test_dispatch_blocks_tool_permission_not_in_allowed_context():
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
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(
        ToolCall(name="write_file", arguments={}, id="call1"),
        ToolContext(allowed_tool_permissions=[ToolPermissionLevel.READ_ONLY.value]),
    )

    assert result.status == "blocked"
    assert "permission not allowed" in result.error
    assert result.metadata["permission_level"] == ToolPermissionLevel.WORKSPACE_WRITE.value


def test_dispatch_maps_nonzero_exit_code_to_error():
    registry = ToolRegistry()
    registry.register(ToolSpec("run_shell", "Run", {"type": "object"}, lambda args, ctx: {"exit_code": 1, "stderr": "bad"}))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="run_shell", arguments={}, id="call1"), ToolContext())

    assert result.status == "error"
    assert result.error == "Command failed with exit_code=1"
    assert result.metadata["failure_type"] == "command_failed"
    assert result.metadata["recoverable"] is True


def test_dispatch_blocks_schema_invalid_arguments_before_handler():
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
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="write_file", arguments={"content": "x"}, id="call1"), ToolContext())

    assert called is False
    assert result.status == "blocked"
    assert result.metadata["schema_valid"] is False
    assert result.metadata["failure_type"] == "schema_validation_failed"
    assert result.metadata["retry_allowed"] is True
    assert "$.path: missing required property" in result.metadata["schema_errors"]


def test_dispatch_marks_schema_valid_on_success():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "echo",
            "Echo",
            {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
            lambda args, ctx: {"ok": args["x"]},
        )
    )
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="echo", arguments={"x": 3}, id="call1"), ToolContext())

    assert result.status == "ok"
    assert result.metadata["schema_valid"] is True


def test_dispatch_blocks_closed_schema_extra_arguments_before_handler():
    called = False

    def handler(args, ctx):
        nonlocal called
        called = True
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "read_file",
            "Read",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler,
        )
    )
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="read_file", arguments={"path": "README.md", "url": "x"}, id="call1"), ToolContext())

    assert called is False
    assert result.status == "blocked"
    assert result.metadata["schema_valid"] is False
    assert "$.url: additional property not allowed" in result.metadata["schema_errors"]
    assert result.metadata["schema_repair_hints"] == ["Remove the unsupported argument at $.url."]
    assert result.metadata["schema_repair_hint_types"] == ["remove_additional_property"]
    assert result.metadata["schema_repair_hint_details"][0]["schema_keyword"] == "additionalProperties"
    assert result.metadata["schema_repair_hint_details"][0]["schema_path"] == "$.url"


def test_builtin_run_command_blocks_empty_command_array_before_runtime(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(ToolCall(name="run_command", arguments={"command": []}, id="call1"), ToolContext())

    assert result.status == "blocked"
    assert result.metadata["schema_valid"] is False
    assert any("minItems 1" in error for error in result.metadata["schema_errors"])


def test_builtin_run_command_blocks_invalid_timeout_before_runtime(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(
        ToolCall(name="run_command", arguments={"command": ["python", "--version"], "timeout": 0}, id="call1"),
        ToolContext(),
    )

    assert result.status == "blocked"
    assert result.metadata["schema_valid"] is False
    assert "$.timeout: value 0 is less than minimum 1" in result.metadata["schema_errors"]


def test_builtin_read_file_blocks_unknown_argument_and_invalid_encoding(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    dispatcher = ToolDispatcher(registry)

    result = dispatcher.dispatch(
        ToolCall(name="read_file", arguments={"path": "README.md", "encoding": "utf-16", "url": "x"}, id="call1"),
        ToolContext(),
    )

    assert result.status == "blocked"
    assert result.metadata["schema_valid"] is False
    assert "$.encoding: value 'utf-16' not in enum ['auto', 'utf-8', 'utf-8-sig']" in result.metadata["schema_errors"]
    assert "$.url: additional property not allowed" in result.metadata["schema_errors"]
