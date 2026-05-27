"""JSON-RPC 2.0 message helpers for MCP stdio transport."""

from __future__ import annotations

import json
from typing import Any


def make_request(method: str, params: dict[str, Any] | None = None, request_id: int | str | None = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request."""
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if request_id is not None:
        msg["id"] = request_id
    return msg


def make_response(request_id: int | str, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error(request_id: int | str | None, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def make_notification(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 notification (no id)."""
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def encode_message(msg: dict[str, Any]) -> str:
    """Serialize a JSON-RPC message to a single line."""
    return json.dumps(msg, ensure_ascii=False) + "\n"


def decode_message(line: str) -> dict[str, Any]:
    """Parse a single JSON-RPC line into a dict."""
    stripped = line.strip()
    if not stripped:
        raise ValueError("Empty line")
    return json.loads(stripped)


class JsonRpcStream:
    """Read/write JSON-RPC messages over an async byte stream."""

    def __init__(self, reader, writer) -> None:
        self._reader = reader
        self._writer = writer
        self._buffer = b""

    async def read_message(self) -> dict[str, Any] | None:
        """Read the next JSON-RPC message (newline-delimited JSON)."""
        while b"\n" not in self._buffer:
            chunk = await self._reader.read(4096)
            if not chunk:
                if self._buffer:
                    # Last message without trailing newline
                    line = self._buffer.decode("utf-8")
                    self._buffer = b""
                    return decode_message(line)
                return None
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return decode_message(line.decode("utf-8"))

    async def write_message(self, msg: dict[str, Any]) -> None:
        """Serialize and send a JSON-RPC message."""
        data = encode_message(msg).encode("utf-8")
        self._writer.write(data)
        await self._writer.drain()
