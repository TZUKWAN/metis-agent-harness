"""Tests for MCP stdio server."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metis.mcp.server import MCPServer
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


def _make_registry():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo input",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}},
            handler=lambda args, ctx: args.get("msg", ""),
        )
    )
    return registry


async def test_handle_initialize_returns_server_info():
    server = MCPServer(_make_registry())
    result = server._handle_initialize({"protocolVersion": "2024-11-05"})

    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "metis-mcp-server"
    assert "tools" in result["capabilities"]


async def test_handle_tools_list_returns_registered_tools():
    server = MCPServer(_make_registry())
    result = server._handle_tools_list({})

    assert len(result["tools"]) == 1
    assert result["tools"][0]["name"] == "echo"
    assert result["tools"][0]["description"] == "Echo input"


async def test_handle_tools_call_invokes_handler():
    server = MCPServer(_make_registry())
    result = await server._handle_tools_call({"name": "echo", "arguments": {"msg": "hello"}})

    assert result["isError"] is False
    assert result["content"][0]["text"] == "hello"


async def test_handle_tools_call_returns_error_for_unknown_tool():
    server = MCPServer(_make_registry())
    result = await server._handle_tools_call({"name": "unknown", "arguments": {}})

    assert result["isError"] is True
    assert "Unknown tool" in result["content"][0]["text"]


async def test_handle_tools_call_returns_error_on_exception():
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="boom",
            description="Boom",
            parameters={"type": "object"},
            handler=lambda args, ctx: (_ for _ in ()).throw(ValueError("fail")),
        )
    )
    server = MCPServer(registry)
    result = await server._handle_tools_call({"name": "boom", "arguments": {}})

    assert result["isError"] is True
    assert "ValueError" in result["content"][0]["text"]


async def test_handle_tools_call_async_handler():
    async def async_handler(args, ctx):
        return "async-result"

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="async_echo",
            description="Async echo",
            parameters={"type": "object"},
            handler=async_handler,
        )
    )
    server = MCPServer(registry)
    result = await server._handle_tools_call({"name": "async_echo", "arguments": {}})

    assert result["isError"] is False
    assert result["content"][0]["text"] == "async-result"


async def test_handle_message_dispatches_initialize():
    server = MCPServer(_make_registry())
    server._initialized = False

    responses = []

    async def capture_response(rid, r):
        responses.append((rid, r))

    with patch.object(server, "_send_response", side_effect=capture_response):
        await server._handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })

    assert server._initialized is True
    assert len(responses) == 1
    assert responses[0][0] == 1
    assert responses[0][1]["serverInfo"]["name"] == "metis-mcp-server"


async def test_handle_message_rejects_non_jsonrpc():
    server = MCPServer(_make_registry())
    errors = []

    async def capture_error(rid, c, m):
        errors.append((rid, c, m))

    with patch.object(server, "_send_error", side_effect=capture_error):
        await server._handle_message({"id": 1, "method": "tools/list"})

    assert len(errors) == 1
    assert errors[0][1] == -32600  # INVALID_REQUEST


async def test_handle_message_rejects_before_initialize():
    server = MCPServer(_make_registry())
    server._initialized = False

    errors = []

    async def capture_error(rid, c, m):
        errors.append((rid, c, m))

    with patch.object(server, "_send_error", side_effect=capture_error):
        await server._handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        })

    assert len(errors) == 1
    assert errors[0][1] == -32001  # NOT_INITIALIZED


async def test_handle_message_allows_initialized_notification():
    server = MCPServer(_make_registry())
    server._initialized = False

    errors = []

    async def capture_error(rid, c, m):
        errors.append((rid, c, m))

    with patch.object(server, "_send_error", side_effect=capture_error):
        await server._handle_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

    assert len(errors) == 0


async def test_handle_message_returns_empty_resources_and_prompts():
    server = MCPServer(_make_registry())
    server._initialized = True

    responses = []

    async def capture_response(rid, r):
        responses.append((rid, r))

    with patch.object(server, "_send_response", side_effect=capture_response):
        await server._handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/list",
        })
        await server._handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "prompts/list",
        })

    assert len(responses) == 2
    assert responses[0][1] == {"resources": []}
    assert responses[1][1] == {"prompts": []}


async def test_handle_message_rejects_unknown_method():
    server = MCPServer(_make_registry())
    server._initialized = True

    errors = []

    async def capture_error(rid, c, m):
        errors.append((rid, c, m))

    with patch.object(server, "_send_error", side_effect=capture_error):
        await server._handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
        })

    assert len(errors) == 1
    assert errors[0][1] == -32601  # METHOD_NOT_FOUND


async def test_run_reads_lines_and_dispatches():
    server = MCPServer(_make_registry())
    server._initialized = True

    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    calls = []

    async def capture_response(rid, r):
        calls.append(r)

    with patch.object(server, "_send_response", side_effect=capture_response):
        q = asyncio.Queue()
        await q.put(line)
        await q.put("")

        original_run = server.run

        async def patched_run():
            while True:
                l = await q.get()
                if not l:
                    break
                try:
                    msg = json.loads(l)
                except (ValueError, json.JSONDecodeError):
                    continue
                await server._handle_message(msg)

        await patched_run()

    assert len(calls) == 1
    assert len(calls[0]["tools"]) == 1
    assert calls[0]["tools"][0]["name"] == "echo"
