"""Deterministic context compression for small-model runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompressionResult:
    messages: list[dict[str, Any]]
    compressed: bool
    original_chars: int
    compressed_chars: int
    summary: str = ""


class SimpleContextCompressor:
    """Keep instructions and recent turns, summarize the middle deterministically."""

    def __init__(self, *, max_summary_chars: int = 4000, keep_recent: int = 8, max_tool_result_chars: int = 8000) -> None:
        self.max_summary_chars = max_summary_chars
        self.keep_recent = keep_recent
        self.max_tool_result_chars = max_tool_result_chars

    def compress(self, messages: list[dict[str, Any]], *, max_chars: int) -> CompressionResult:
        original_chars = self._count_chars(messages)
        if original_chars <= max_chars:
            return CompressionResult(
                messages=list(messages),
                compressed=False,
                original_chars=original_chars,
                compressed_chars=original_chars,
            )

        trimmed = self._trim_large_tool_results(messages)
        trimmed_chars = self._count_chars(trimmed)
        if trimmed_chars <= max_chars:
            return CompressionResult(
                messages=trimmed,
                compressed=True,
                original_chars=original_chars,
                compressed_chars=trimmed_chars,
                summary="Trimmed large tool results",
            )

        system_messages = [msg for msg in trimmed if msg.get("role") == "system"]
        non_system = [msg for msg in messages if msg.get("role") != "system"]
        recent = non_system[-self.keep_recent :] if self.keep_recent > 0 else []
        middle = non_system[: max(0, len(non_system) - len(recent))]
        summary = self._summarize(middle)
        summary_message = {
            "role": "system",
            "content": (
                "Context compression summary. Earlier conversation and tool outputs were compacted "
                "to preserve the working state:\n"
                f"{summary}"
            ),
            "metadata": {"metis_context_summary": True},
        }

        compressed_messages = system_messages + [summary_message] + recent
        while self._count_chars(compressed_messages) > max_chars and len(recent) > 1:
            recent = recent[1:]
            compressed_messages = system_messages + [summary_message] + recent

        if self._count_chars(compressed_messages) > max_chars:
            compressed_messages = self._force_fit(compressed_messages, max_chars)

        compressed_chars = self._count_chars(compressed_messages)
        return CompressionResult(
            messages=compressed_messages,
            compressed=True,
            original_chars=original_chars,
            compressed_chars=compressed_chars,
            summary=summary,
        )

    def _trim_large_tool_results(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages:
            if message.get("role") != "tool":
                result.append(message)
                continue
            content = str(message.get("content", ""))
            limit = self.max_tool_result_chars
            if self._is_critical_tool_result(message):
                limit = limit * 3
            if len(content) <= limit:
                result.append(message)
                continue
            trimmed = content[:limit]
            summary_line = f"\n... [trimmed {len(content) - limit} chars]"
            cloned = dict(message)
            cloned["content"] = trimmed + summary_line
            result.append(cloned)
        return result

    @staticmethod
    def _is_critical_tool_result(message: dict[str, Any]) -> bool:
        """Identify tool results that should be preserved for model self-correction."""
        content = str(message.get("content", ""))
        status = str(message.get("status", ""))
        if status in ("blocked", "failed", "error"):
            return True
        if '"error"' in content or '"error_type"' in content:
            return True
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                if "error" in data or "error_type" in data:
                    return True
                if data.get("status") in ("blocked", "failed", "error"):
                    return True
                if "written" in data or "created" in data or "deleted" in data:
                    return True
        except (json.JSONDecodeError, ValueError):
            pass
        return False

    def _summarize(self, messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for index, message in enumerate(messages, start=1):
            role = str(message.get("role", "unknown"))
            content = str(message.get("content", ""))
            if not content:
                continue
            prefix = ""
            if role == "tool":
                tool_name = message.get("name", "unknown")
                if self._is_critical_tool_result(message):
                    prefix = "[CRITICAL] "
                one_line = f"[{tool_name}] {self._tool_summary(content)}"
            else:
                one_line = " ".join(content.split())
            if len(one_line) > 300:
                one_line = one_line[:297] + "..."
            lines.append(f"{index}. {role}: {prefix}{one_line}")
        summary = "\n".join(lines)
        if len(summary) > self.max_summary_chars:
            return summary[: self.max_summary_chars - 4] + "\n..."
        return summary

    @staticmethod
    def _tool_summary(content: str) -> str:
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                if "error" in data:
                    return f"Error: {data['error']}"
                if "path" in data and "written" in data:
                    return f"Wrote {data['path']}"
                if "path" in data and "content" in data:
                    text = str(data.get("content", ""))
                    preview = text[:80] + "..." if len(text) > 80 else text
                    return f"Read {data['path']}: {preview}"
                if "exit_code" in data:
                    return f"Exit {data['exit_code']}"
                if "matches" in data and "count" in data:
                    return f"Search: {data['count']} matches"
                if "files" in data and "count" in data:
                    return f"Find: {data['count']} files"
                if "total_lines" in data:
                    return f"Lines: {data['total_lines']} total, {data.get('non_empty_lines', '?')} non-empty"
                if "size" in data and "is_file" in data:
                    return f"FileInfo: {data.get('name', '?')} size={data['size']}"
                if "result" in data:
                    result = data["result"]
                    text = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                    return text[:100] + "..." if len(text) > 100 else text
        except (json.JSONDecodeError, ValueError):
            pass
        text = " ".join(content.split())
        return text[:100] + "..." if len(text) > 100 else text

    @staticmethod
    def _count_chars(messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += len(str(message.get("content", "")))
            total += len(str(message.get("reasoning_content", "")))
        return total

    @staticmethod
    def _score_message(message: dict[str, Any], index: int, total: int) -> int:
        """Score message importance for eviction priority. Higher = more important."""
        role = str(message.get("role", ""))
        if role == "system":
            return 100
        if role == "user":
            return 80
        if role == "assistant":
            if "tool_calls" in message:
                return 70
            if message.get("reasoning_content"):
                return 65
            return 50
        if role == "tool":
            if SimpleContextCompressor._is_critical_tool_result(message):
                return 90
            if index >= total - 4:
                return 75
            return 40
        return 30

    @classmethod
    def _force_fit(cls, messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
        remaining = max(0, max_chars)
        total = len(messages)
        scored = [
            (cls._score_message(msg, idx, total), idx, msg)
            for idx, msg in enumerate(messages)
        ]
        system_msgs = [(s, i, m) for s, i, m in scored if m.get("role") == "system"]
        non_system = [(s, i, m) for s, i, m in scored if m.get("role") != "system"]
        non_system.sort(key=lambda x: x[0], reverse=True)
        sorted_msgs = system_msgs + non_system

        fitted: list[tuple[int, dict[str, Any]]] = []
        for _score, idx, message in sorted_msgs:
            if remaining <= 0:
                break
            content = str(message.get("content", ""))
            if len(content) > remaining:
                content = content[: max(0, remaining - 4)] + "\n..."
            cloned = dict(message)
            cloned["content"] = content
            fitted.append((idx, cloned))
            remaining -= len(content)

        fitted.sort(key=lambda item: item[0])
        return [m for _i, m in fitted]
