"""Parser for JSON tool-call blocks in plain model text."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from metis.providers.parsers.base import ToolCallParser
from metis.runtime.response import ToolCall

FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class JsonBlockParser(ToolCallParser):
    def parse(self, raw: Any) -> list[ToolCall]:
        text = raw if isinstance(raw, str) else str(raw or "")
        payloads = [m.group(1) for m in FENCED_JSON_RE.finditer(text)]
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payloads.append(stripped)

        calls: list[ToolCall] = []
        for payload_text in payloads:
            payload = json.loads(payload_text)
            name = payload.get("name") or payload.get("tool")
            args = payload.get("arguments", payload.get("args", {}))
            if name and isinstance(args, dict):
                calls.append(ToolCall(name=name, arguments=args, id=payload.get("id", uuid.uuid4().hex[:8]), raw=payload))
        return calls
