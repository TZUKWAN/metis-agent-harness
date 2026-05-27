"""MCP (Model Context Protocol) integration for Metis Agent Harness.

Provides lightweight JSON-RPC 2.0 client and server over stdio,
allowing Metis to consume external MCP tools and expose its own tools
to MCP-compatible hosts.
"""

from __future__ import annotations

from metis.mcp.client import MCPClient
from metis.mcp.server import MCPServer
from metis.mcp.spec import MCPTool, MCPResource, MCPServerConfig

__all__ = [
    "MCPClient",
    "MCPServer",
    "MCPTool",
    "MCPResource",
    "MCPServerConfig",
]
