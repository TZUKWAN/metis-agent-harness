"""MCP stdio server that exposes Metis tools to MCP-compatible hosts."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from typing import Any

from metis.mcp.errors import MCPError, MCPErrorCode
from metis.mcp.protocol import decode_message, encode_message, make_error, make_response
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


class MCPServer:
    """Expose Metis tools as an MCP server over stdio."""

    def __init__(
        self,
        registry: ToolRegistry,
        name: str = "metis-mcp-server",
        version: str = "0.2.0",
    ) -> None:
        self.registry = registry
        self.name = name
        self.version = version
        self._initialized = False
        self._write_lock = asyncio.Lock()

    async def run(self) -> None:
        """Run the MCP server loop reading from stdin and writing to stdout."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str] = asyncio.Queue()

        def _reader() -> None:
            try:
                for line in sys.stdin:
                    line = line.strip()
                    if line:
                        loop.call_soon_threadsafe(queue.put_nowait, line)
            except Exception:
                pass
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, "")

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        while True:
            line = await queue.get()
            if not line:
                break
            try:
                msg = decode_message(line)
            except (ValueError, json.JSONDecodeError):
                continue
            await self._handle_message(msg)

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        """Dispatch a single JSON-RPC message."""
        if msg.get("jsonrpc") != "2.0":
            if "id" in msg:
                await self._send_error(msg["id"], MCPErrorCode.INVALID_REQUEST, "Invalid JSON-RPC request")
            return

        method = msg.get("method")
        params = msg.get("params", {})
        request_id = msg.get("id")

        # Notifications have no id
        is_notification = request_id is None

        if method == "initialize":
            result = self._handle_initialize(params)
            self._initialized = True
            if not is_notification:
                await self._send_response(request_id, result)
            return

        if method == "notifications/initialized":
            # Client confirms initialization - no response needed
            return

        if not self._initialized:
            if not is_notification:
                await self._send_error(
                    request_id, MCPErrorCode.NOT_INITIALIZED, "Server not initialized"
                )
            return

        if method == "tools/list":
            result = self._handle_tools_list(params)
        elif method == "tools/call":
            try:
                result = await self._handle_tools_call(params)
            except Exception as exc:
                if not is_notification:
                    await self._send_error(
                        request_id, MCPErrorCode.INTERNAL_ERROR, f"Tool call failed: {exc}"
                    )
                return
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            if not is_notification:
                await self._send_error(
                    request_id, MCPErrorCode.METHOD_NOT_FOUND, f"Method not found: {method}"
                )
            return

        if not is_notification:
            await self._send_response(request_id, result)

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the initialize request."""
        return {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the list of available tools."""
        tools = []
        for spec in self.registry.iter_specs():
            tools.append({
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.parameters,
            })
        return {"tools": tools}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Call a Metis tool and return the result."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        spec = self.registry.get(tool_name)
        if spec is None:
            return {
                "content": [
                    {"type": "error", "text": f"Unknown tool: {tool_name}"}
                ],
                "isError": True,
            }

        ctx = ToolContext()
        try:
            raw = spec.handler(arguments, ctx)
            if asyncio.iscoroutine(raw):
                raw = await raw
        except Exception as exc:
            return {
                "content": [
                    {"type": "error", "text": f"{type(exc).__name__}: {exc}"}
                ],
                "isError": True,
            }

        text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        }

    async def _send_response(self, request_id: int | str, result: Any) -> None:
        async with self._write_lock:
            sys.stdout.write(encode_message(make_response(request_id, result)))
            sys.stdout.flush()

    async def _send_error(
        self, request_id: int | str | None, code: int, message: str
    ) -> None:
        async with self._write_lock:
            sys.stdout.write(encode_message(make_error(request_id, code, message)))
            sys.stdout.flush()
