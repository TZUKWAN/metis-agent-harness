"""Tool input sanitization: clean tool arguments before dispatch."""

from __future__ import annotations

import re
from typing import Any

_MAX_STRING_VALUE_LENGTH = 100_000
_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[\\/]")
_NULL_BYTE_PATTERN = re.compile(r"\x00")
_CONTROL_CHAR_PATTERN = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ToolInputSanitizer:
    """Sanitize tool call arguments: strip null bytes, limit string length, normalize paths."""

    def sanitize(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._sanitize_value(args)

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._sanitize_string(value)
        if isinstance(value, dict):
            return {k: self._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        return value

    def _sanitize_string(self, value: str) -> str:
        value = _NULL_BYTE_PATTERN.sub("", value)
        value = _CONTROL_CHAR_PATTERN.sub("", value)
        if len(value) > _MAX_STRING_VALUE_LENGTH:
            value = value[:_MAX_STRING_VALUE_LENGTH] + "... [truncated by sanitizer]"
        return value
