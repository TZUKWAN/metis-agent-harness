"""Tests for MCP spec dataclasses and helpers."""

from metis.mcp.spec import (
    MCPServerConfig,
    MCPTool,
    mcp_tools_from_list_response,
)


def test_mcp_server_config_defaults():
    config = MCPServerConfig(name="test-server", command=["python", "server.py"])

    assert config.name == "test-server"
    assert config.command == ["python", "server.py"]
    assert config.env == {}
    assert config.description_prefix == ""


def test_mcp_server_config_with_env_and_prefix():
    config = MCPServerConfig(
        name="test-server",
        command=["node", "server.js"],
        env={"KEY": "value"},
        description_prefix="[ext]",
    )

    assert config.env == {"KEY": "value"}
    assert config.description_prefix == "[ext]"


def test_mcp_tool_from_dict():
    tool = MCPTool.from_dict({
        "name": "read_file",
        "description": "Read a file",
        "inputSchema": {"type": "object", "properties": {}},
    })

    assert tool.name == "read_file"
    assert tool.description == "Read a file"
    assert tool.input_schema == {"type": "object", "properties": {}}


def test_mcp_tool_from_dict_fallback_input_schema():
    tool = MCPTool.from_dict({
        "name": "write_file",
        "description": "Write a file",
    })

    assert tool.input_schema == {"type": "object"}


def test_mcp_tool_to_metis_spec():
    tool = MCPTool(
        name="read_file",
        description="Read a file",
        input_schema={"type": "object"},
    )

    def handler(args, ctx):
        return "ok"

    spec = tool.to_metis_spec(handler)

    assert spec.name == "read_file"
    assert spec.description == "Read a file"
    assert spec.parameters == {"type": "object"}
    assert spec.handler is handler
    assert spec.category == "mcp"
    assert spec.side_effect == "read"
    assert spec.permission_level == "read_only"
    assert spec.metadata == {"mcp_tool": True}


def test_mcp_tools_from_list_response():
    response = {
        "tools": [
            {"name": "a", "description": "Tool A", "inputSchema": {"type": "object"}},
            {"name": "b", "description": "Tool B", "inputSchema": {"type": "object"}},
        ]
    }

    tools = mcp_tools_from_list_response(response)

    assert len(tools) == 2
    assert tools[0].name == "a"
    assert tools[1].name == "b"


def test_mcp_tools_from_list_response_empty():
    tools = mcp_tools_from_list_response({})

    assert tools == []
