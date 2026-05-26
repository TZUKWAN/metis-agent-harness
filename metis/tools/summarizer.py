"""Lightweight summarization for large tool results."""

from __future__ import annotations

import json
from typing import Any


_MAX_SUMMARY_CHARS = 800


def summarize_tool_result(content: str, tool_name: str) -> str:
    """Return a compact summary of a large tool result."""
    if len(content) <= _MAX_SUMMARY_CHARS:
        return content

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _summarize_dict(data, tool_name)
        if isinstance(data, list):
            return _summarize_list(data, tool_name)
    except (json.JSONDecodeError, ValueError):
        pass

    return _summarize_text(content, tool_name)


def _summarize_dict(data: dict[str, Any], tool_name: str) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if key in ("content", "stdout", "stderr", "result", "output"):
            text = str(value)
            if len(text) > 120:
                text = text[:120] + "..."
            lines.append(f"{key}: {text}")
        elif isinstance(value, list):
            lines.append(f"{key}: [{len(value)} items]")
        elif isinstance(value, dict):
            lines.append(f"{key}: {{{len(value)} keys}}")
        else:
            lines.append(f"{key}: {value}")
    summary = " | ".join(lines[:12])
    if len(lines) > 12:
        summary += f" ... ({len(lines) - 12} more keys)"
    return summary


def _summarize_list(data: list[Any], tool_name: str) -> str:
    if not data:
        return "[]"
    sample = json.dumps(data[:3], ensure_ascii=False)
    if len(sample) > 200:
        sample = sample[:200] + "..."
    return f"[{len(data)} items] first 3: {sample}"


def _summarize_text(content: str, tool_name: str) -> str:
    lines = content.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    head = non_empty[:8]
    tail = non_empty[-3:] if len(non_empty) > 11 else []
    parts = head
    if tail and len(non_empty) > 11:
        parts.append("...")
        parts.extend(tail)
    summary = "\n".join(parts)
    return f"[{tool_name}] Summary ({len(non_empty)} lines, {len(content)} chars):\n" + summary
