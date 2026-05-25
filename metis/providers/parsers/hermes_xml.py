"""Parser for <tool_call>{...}</tool_call> text blocks."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from metis.providers.parsers.base import ToolCallParser
from metis.runtime.errors import ParserError
from metis.runtime.response import ToolCall

TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


class HermesXMLParser(ToolCallParser):
    def parse(self, raw: Any) -> list[ToolCall]:
        text = raw if isinstance(raw, str) else str(raw or "")
        calls: list[ToolCall] = []
        for match in TOOL_CALL_RE.finditer(text):
            payload = json.loads(match.group(1))
            name = payload.get("name") or payload.get("tool")
            args = payload.get("arguments", payload.get("args", {}))
            if not name:
                raise ParserError("Tool call is missing name")
            if not isinstance(args, dict):
                raise ParserError("Tool call arguments must be an object")
            calls.append(ToolCall(name=name, arguments=args, id=payload.get("id", uuid.uuid4().hex[:8]), raw=payload))
        return calls
