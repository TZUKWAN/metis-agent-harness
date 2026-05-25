from metis.runtime.profiles import get_model_profile
from metis.tools.registry import ToolRegistry
from metis.tools.builtin import register_builtin_tools
from metis.tools.spec import ToolSpec
from metis.tools.tool_router import ToolRouteRequest, ToolRouter


def test_tool_router_limits_small_profile_to_relevant_tools():
    registry = ToolRegistry()
    for index in range(100):
        category = "filesystem" if index % 2 == 0 else "network"
        registry.register(
            ToolSpec(
                name=f"tool_{index:03d}",
                description="Tool",
                parameters={"type": "object"},
                handler=lambda args, ctx: args,
                category=category,
            )
        )

    routed = ToolRouter(registry).route(ToolRouteRequest(stage="explore", profile=get_model_profile("small")))

    assert len(routed) <= 8
    assert all(tool.category in {"filesystem", "search", "shell", "general", "test"} for tool in routed)


def test_tool_router_respects_allowed_tools():
    registry = ToolRegistry()
    registry.register(ToolSpec("read", "Read", {"type": "object"}, lambda args, ctx: args, category="filesystem"))
    registry.register(ToolSpec("write", "Write", {"type": "object"}, lambda args, ctx: args, category="filesystem"))

    routed = ToolRouter(registry).route(ToolRouteRequest(stage="execute", allowed_tools=["write"]))

    assert [tool.name for tool in routed] == ["write"]


def test_tool_router_includes_builtin_file_tools_without_allowed_filter(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))

    routed = ToolRouter(registry).route(ToolRouteRequest(stage="execute", profile="small"))
    names = {tool.name for tool in routed}

    assert "read_file" in names
    assert "write_file" in names
