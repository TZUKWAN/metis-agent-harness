"""Parser for OpenAI native tool_calls structures."""

from __future__ import annotations

import json
from typing import Any

from metis.providers.parsers.base import ToolCallParser
from metis.runtime.response import ToolCall


class OpenAINativeParser(ToolCallParser):
    def parse(self, raw: Any) -> list[ToolCall]:
        if not raw:
            return []
        calls = []
        for item in raw:
            function = item.get("function", {}) if isinstance(item, dict) else getattr(item, "function", None)
            call_id = item.get("id", "") if isinstance(item, dict) else getattr(item, "id", "")
            if not isinstance(function, dict):
                name = getattr(function, "name", "")
                arguments_raw = getattr(function, "arguments", "{}")
            else:
                name = function.get("name", "")
                arguments_raw = function.get("arguments", "{}")
            arguments = json.loads(arguments_raw or "{}") if isinstance(arguments_raw, str) else dict(arguments_raw)
            calls.append(ToolCall(name=name, arguments=arguments, id=call_id, raw=item))
        return calls
