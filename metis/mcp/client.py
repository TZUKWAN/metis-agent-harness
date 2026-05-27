"""MCP stdio client for connecting to external MCP servers."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from metis.mcp.errors import MCPError, MCPErrorCode
from metis.mcp.protocol import JsonRpcStream, make_notification, make_request
from metis.mcp.spec import MCPServerConfig, MCPTool, mcp_tools_from_list_response


class MCPClient:
    """Connects to an MCP server via stdio and exposes its tools."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._stream: JsonRpcStream | None = None
        self._request_counter = 0
        self._initialized = False

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None and self._initialized

    async def connect(self, timeout: float = 10.0) -> None:
        """Launch the MCP server process and perform the initialization handshake."""
        if self.is_connected:
            raise MCPError(MCPErrorCode.ALREADY_INITIALIZED, "Client already connected")

        env = {**os.environ, **self.config.env}
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE if sys.stderr is not None else None,
                env=env,
            )
        except FileNotFoundError as exc:
            raise MCPError(
                MCPErrorCode.INITIALIZATION_ERROR,
                f"Failed to start MCP server '{self.config.name}': {exc}",
            ) from exc

        self._stream = JsonRpcStream(self._process.stdout, self._process.stdin)

        # Send initialize request
        init_request = make_request(
            "initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "metis-mcp-client", "version": "0.2.0"},
            },
            request_id=self._next_id(),
        )

        try:
            await asyncio.wait_for(self._stream.write_message(init_request), timeout=timeout)
        except asyncio.TimeoutError as exc:
            await self._terminate()
            raise MCPError(
                MCPErrorCode.INITIALIZATION_ERROR,
                f"MCP server '{self.config.name}' initialize request timed out",
            ) from exc

        # Read initialize response
        try:
            response = await asyncio.wait_for(self._stream.read_message(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            await self._terminate()
            raise MCPError(
                MCPErrorCode.INITIALIZATION_ERROR,
                f"MCP server '{self.config.name}' initialize response timed out",
            ) from exc

        if response is None:
            await self._terminate()
            raise MCPError(
                MCPErrorCode.INITIALIZATION_ERROR,
                f"MCP server '{self.config.name}' closed stream during initialization",
            )

        error = response.get("error")
        if error is not None:
            await self._terminate()
            raise MCPError(
                error.get("code", MCPErrorCode.INTERNAL_ERROR),
                error.get("message", "Unknown initialization error"),
            )

        # Send initialized notification
        await self._stream.write_message(
            make_notification("notifications/initialized")
        )
        self._initialized = True

    async def list_tools(self) -> list[MCPTool]:
        """List available tools from the MCP server."""
        if not self.is_connected:
            raise MCPError(MCPErrorCode.NOT_INITIALIZED, "Client not connected")

        request_id = self._next_id()
        await self._stream.write_message(make_request("tools/list", {}, request_id))
        response = await self._stream.read_message()

        if response is None:
            raise MCPError(
                MCPErrorCode.INTERNAL_ERROR,
                f"MCP server '{self.config.name}' closed stream during tools/list",
            )

        error = response.get("error")
        if error is not None:
            raise MCPError(
                error.get("code", MCPErrorCode.INTERNAL_ERROR),
                error.get("message", "tools/list failed"),
            )

        return mcp_tools_from_list_response(response.get("result", {}))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool and return its text content."""
        if not self.is_connected:
            raise MCPError(MCPErrorCode.NOT_INITIALIZED, "Client not connected")

        request_id = self._next_id()
        await self._stream.write_message(
            make_request("tools/call", {"name": name, "arguments": arguments}, request_id)
        )
        response = await self._stream.read_message()

        if response is None:
            raise MCPError(
                MCPErrorCode.INTERNAL_ERROR,
                f"MCP server '{self.config.name}' closed stream during tools/call",
            )

        error = response.get("error")
        if error is not None:
            raise MCPError(
                error.get("code", MCPErrorCode.INTERNAL_ERROR),
                error.get("message", f"tools/call for '{name}' failed"),
            )

        result = response.get("result", {})
        content = result.get("content", [])

        # content is a list of {type, text} or {type, data} dicts
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(str(item.get("text", "")))
                elif item.get("type") == "error":
                    texts.append(f"[error] {item.get('text', '')}")
                else:
                    texts.append(str(item))
            else:
                texts.append(str(item))

        return "\n".join(texts) if texts else ""

    async def close(self) -> None:
        """Terminate the MCP server process and clean up."""
        await self._terminate()

    def _next_id(self) -> int:
        self._request_counter += 1
        return self._request_counter

    async def _terminate(self) -> None:
        self._initialized = False
        if self._process is None:
            return
        try:
            if self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
        except ProcessLookupError:
            pass
        finally:
            self._process = None
            self._stream = None


async def connect_mcp_clients(
    configs: list[MCPServerConfig],
    *,
    timeout: float = 10.0,
) -> tuple[list[MCPClient], list[str]]:
    """Connect to multiple MCP servers and return (connected_clients, errors)."""
    clients: list[MCPClient] = []
    errors: list[str] = []

    for config in configs:
        client = MCPClient(config)
        try:
            await client.connect(timeout=timeout)
            clients.append(client)
        except MCPError as exc:
            errors.append(f"MCP server '{config.name}': {exc.message}")
        except Exception as exc:
            errors.append(f"MCP server '{config.name}': {type(exc).__name__}: {exc}")

    return clients, errors


async def register_mcp_tools(
    registry: Any,
    clients: list[MCPClient],
) -> dict[str, int]:
    """Register MCP tools from connected clients into a Metis ToolRegistry.

    Returns a dict mapping client name to tool count.
    """
    counts: dict[str, int] = {}
    for client in clients:
        try:
            tools = await client.list_tools()
        except MCPError:
            counts[client.config.name] = 0
            continue

        registered = 0
        for tool in tools:
            handler = _make_mcp_handler(client, tool.name)
            spec = tool.to_metis_spec(handler)
            if client.config.description_prefix:
                spec.description = f"{client.config.description_prefix} {spec.description}"

            # Namespace the tool name to avoid collisions
            namespaced_name = f"{client.config.name}__{tool.name}"
            spec.name = namespaced_name
            registry.register(spec, overwrite=True)
            registered += 1

        counts[client.config.name] = registered

    return counts


def _make_mcp_handler(client: MCPClient, tool_name: str):
    """Build a sync Metis handler that calls an async MCP tool via asyncio.run()."""

    def handler(args: dict[str, Any], context: Any) -> str:
        return asyncio.run(client.call_tool(tool_name, args))

    return handler
