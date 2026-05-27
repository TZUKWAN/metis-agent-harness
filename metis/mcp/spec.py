"""MCP data types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metis.tools.spec import ToolSpec, ToolContext


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server."""

    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    description_prefix: str = ""


@dataclass
class MCPTool:
    """An MCP tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPTool":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {"type": "object"})),
        )

    def to_metis_spec(self, handler) -> ToolSpec:
        """Convert to a Metis ToolSpec with the given handler."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.input_schema,
            handler=handler,
            category="mcp",
            side_effect="read",
            permission_level="read_only",
            metadata={"mcp_tool": True},
        )


@dataclass
class MCPResource:
    """An MCP resource definition."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


def mcp_tools_from_list_response(response: dict[str, Any]) -> list[MCPTool]:
    """Extract MCPTool list from a tools/list response."""
    tools = response.get("tools", [])
    return [MCPTool.from_dict(t) for t in tools]


def build_mcp_tool_handler(client: "MCPClient", tool_name: str):
    """Build a Metis handler that delegates to an MCP client."""
    async def handler(args: dict[str, Any], context: ToolContext) -> str:
        result = await client.call_tool(tool_name, args)
        return result

    return handler
