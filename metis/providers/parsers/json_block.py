"""Parser for JSON tool-call blocks in plain model text."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from metis.providers.parsers.base import ToolCallParser
from metis.runtime.response import ToolCall

FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

TOOL_CALL_PATTERNS = [
    re.compile(r'"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})', re.DOTALL),
    re.compile(r'"tool"\s*:\s*"(\w+)"\s*,\s*"args"\s*:\s*(\{[^}]*\})', re.DOTALL),
]


def _try_repair_json(text: str) -> dict | None:
    """Attempt to repair common JSON issues from 8B model output."""
    text = text.strip()
    if not text.startswith("{"):
        brace_start = text.find("{")
        if brace_start >= 0:
            text = text[brace_start:]
    if not text.endswith("}"):
        brace_end = text.rfind("}")
        if brace_end >= 0:
            text = text[: brace_end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    text = re.sub(r"[\x00-\x1f]+", " ", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class JsonBlockParser(ToolCallParser):
    def parse(self, raw: Any) -> list[ToolCall]:
        text = raw if isinstance(raw, str) else str(raw or "")
        calls: list[ToolCall] = []
        payloads = [m.group(1) for m in FENCED_JSON_RE.finditer(text)]
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payloads.append(stripped)

        for payload_text in payloads:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                payload = _try_repair_json(payload_text)
            if not isinstance(payload, dict):
                continue
            name = payload.get("name") or payload.get("tool")
            args = payload.get("arguments", payload.get("args", {}))
            if name and isinstance(args, dict):
                calls.append(ToolCall(name=name, arguments=args, id=payload.get("id", uuid.uuid4().hex[:8]), raw=payload))

        if not calls:
            for pattern in TOOL_CALL_PATTERNS:
                for match in pattern.finditer(text):
                    name = match.group(1)
                    args_raw = match.group(2)
                    args = _try_repair_json(args_raw)
                    if name and isinstance(args, dict):
                        calls.append(ToolCall(name=name, arguments=args, id=uuid.uuid4().hex[:8], raw=match.group(0)))
        return calls
