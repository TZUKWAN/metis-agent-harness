"""Tests for MCP client connection and tool calls."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metis.mcp.client import MCPClient, connect_mcp_clients, register_mcp_tools
from metis.mcp.errors import MCPError, MCPErrorCode
from metis.mcp.spec import MCPServerConfig
from metis.tools.registry import ToolRegistry


@pytest.fixture
def config():
    return MCPServerConfig(name="test-server", command=["python", "-c", "pass"])


async def test_connect_launches_process_and_handshakes(config, monkeypatch):
    client = MCPClient(config)

    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()

    init_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "test", "version": "1.0"},
        },
    }
    mock_stream.read_message = AsyncMock(return_value=init_response)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("metis.mcp.client.JsonRpcStream", return_value=mock_stream):
            await client.connect(timeout=5.0)

    assert client.is_connected
    mock_stream.write_message.assert_awaited()


async def test_connect_raises_on_process_failure(config):
    client = MCPClient(config)

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("not found")):
        with pytest.raises(MCPError) as exc_info:
            await client.connect()

    assert exc_info.value.code == MCPErrorCode.INITIALIZATION_ERROR


async def test_connect_raises_on_init_timeout(config):
    client = MCPClient(config)

    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock()

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()
    mock_stream.read_message = AsyncMock(side_effect=asyncio.TimeoutError)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("metis.mcp.client.JsonRpcStream", return_value=mock_stream):
            with pytest.raises(MCPError) as exc_info:
                await client.connect(timeout=0.01)

    assert exc_info.value.code == MCPErrorCode.INITIALIZATION_ERROR


async def test_connect_raises_on_init_error_response(config):
    client = MCPClient(config)

    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.stdin = MagicMock()
    mock_process.stdout = MagicMock()
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock()

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()
    mock_stream.read_message = AsyncMock(return_value={"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "Bad request"}})

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("metis.mcp.client.JsonRpcStream", return_value=mock_stream):
            with pytest.raises(MCPError) as exc_info:
                await client.connect()

    assert exc_info.value.code == -32600


async def test_list_tools_returns_parsed_tools(config):
    client = MCPClient(config)
    client._initialized = True
    client._process = MagicMock(returncode=None)

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()
    mock_stream.read_message = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [
                {"name": "read_file", "description": "Read", "inputSchema": {"type": "object"}},
            ]
        },
    })
    client._stream = mock_stream

    tools = await client.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "read_file"


async def test_list_tools_raises_when_not_connected(config):
    client = MCPClient(config)

    with pytest.raises(MCPError) as exc_info:
        await client.list_tools()

    assert exc_info.value.code == MCPErrorCode.NOT_INITIALIZED


async def test_call_tool_returns_text_content(config):
    client = MCPClient(config)
    client._initialized = True
    client._process = MagicMock(returncode=None)

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()
    mock_stream.read_message = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]
        },
    })
    client._stream = mock_stream

    result = await client.call_tool("echo", {"msg": "hi"})

    assert result == "Hello\nWorld"


async def test_call_tool_returns_error_text(config):
    client = MCPClient(config)
    client._initialized = True
    client._process = MagicMock(returncode=None)

    mock_stream = MagicMock()
    mock_stream.write_message = AsyncMock()
    mock_stream.read_message = AsyncMock(return_value={
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "error", "text": "Something broke"},
            ]
        },
    })
    client._stream = mock_stream

    result = await client.call_tool("bad", {})

    assert "[error] Something broke" in result


async def test_call_tool_raises_when_not_connected(config):
    client = MCPClient(config)

    with pytest.raises(MCPError) as exc_info:
        await client.call_tool("echo", {})

    assert exc_info.value.code == MCPErrorCode.NOT_INITIALIZED


async def test_close_terminates_process(config):
    client = MCPClient(config)
    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock()
    client._process = mock_process
    client._initialized = True

    await client.close()

    assert not client.is_connected
    mock_process.terminate.assert_called_once()


async def test_connect_mcp_clients_returns_connected_and_errors():
    configs = [
        MCPServerConfig(name="good", command=["echo"]),
        MCPServerConfig(name="bad", command=["nonexistent_binary_12345"]),
    ]

    class FakeClient:
        def __init__(self, config):
            self.config = config
            self._initialized = False

        async def connect(self, timeout=10.0):
            if self.config.name == "bad":
                raise MCPError(MCPErrorCode.INITIALIZATION_ERROR, "fail")
            self._initialized = True

        @property
        def is_connected(self):
            return self._initialized

        async def close(self):
            pass

    with patch("metis.mcp.client.MCPClient", FakeClient):
        clients, errors = await connect_mcp_clients(configs)

    assert len(clients) == 1
    assert clients[0].config.name == "good"
    assert len(errors) == 1
    assert "bad" in errors[0]


async def test_register_mcp_tools_namespaces_and_prefixes():
    registry = ToolRegistry()
    client = MagicMock()
    client.config = MCPServerConfig(name="ext", command=["echo"], description_prefix="[EXT]")

    tool = MagicMock()
    tool.name = "read_file"
    tool.to_metis_spec.return_value = MagicMock()
    tool.to_metis_spec.return_value.name = "read_file"
    tool.to_metis_spec.return_value.description = "Read a file"

    with patch.object(client, "list_tools", new_callable=AsyncMock, return_value=[tool]):
        counts = await register_mcp_tools(registry, [client])

    assert counts["ext"] == 1
    spec = registry.get("ext__read_file")
    assert spec is not None
    assert spec.description.startswith("[EXT]")
