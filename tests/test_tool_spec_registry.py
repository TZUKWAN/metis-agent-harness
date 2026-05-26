"""Tests for metis/tools/spec.py and metis/tools/registry.py."""

from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec, ToolContext, ToolPermissionLevel


def test_tool_spec_creation():
    spec = ToolSpec(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
        handler=lambda args, ctx: {"result": args["x"]},
        category="test",
        side_effect="read",
        permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
    )
    assert spec.name == "test_tool"
    assert spec.category == "test"


def test_tool_context_defaults():
    ctx = ToolContext()
    assert ctx.hooks is None
    assert ctx.workspace == "."


def test_registry_register_and_get():
    registry = ToolRegistry()
    spec = ToolSpec(
        name="my_tool",
        description="desc",
        parameters={"type": "object", "properties": {}},
        handler=lambda args, ctx: {},
        category="test",
    )
    registry.register(spec)
    assert registry.get("my_tool") is spec


def test_registry_list_tools():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="a", description="a", parameters={"type": "object"}, handler=lambda args, ctx: {}, category="test"))
    registry.register(ToolSpec(name="b", description="b", parameters={"type": "object"}, handler=lambda args, ctx: {}, category="test"))
    tools = registry.list_tools()
    assert "a" in tools
    assert "b" in tools


def test_registry_get_unknown():
    registry = ToolRegistry()
    assert registry.get("unknown") is None


def test_tool_spec_default_values():
    spec = ToolSpec(
        name="x",
        description="x",
        parameters={"type": "object"},
        handler=lambda args, ctx: {},
    )
    assert spec.category == "general"
    assert spec.side_effect == "read"
    assert spec.permission_level == ToolPermissionLevel.READ_ONLY.value
    assert spec.max_result_chars is None
