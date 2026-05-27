"""MCP error codes and helpers."""

from __future__ import annotations


class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific
    INITIALIZATION_ERROR = -32000
    NOT_INITIALIZED = -32001
    ALREADY_INITIALIZED = -32002


class MCPError(Exception):
    def __init__(self, code: int, message: str, data: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(message)

    def to_json(self) -> dict:
        error: dict = {"code": self.code, "message": self.message}
        if self.data:
            error["data"] = self.data
        return error
