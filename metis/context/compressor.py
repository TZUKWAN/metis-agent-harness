"""Deterministic context compression for small-model runs."""

from __future__ import annotations

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

    def __init__(self, *, max_summary_chars: int = 4000, keep_recent: int = 8) -> None:
        self.max_summary_chars = max_summary_chars
        self.keep_recent = keep_recent

    def compress(self, messages: list[dict[str, Any]], *, max_chars: int) -> CompressionResult:
        original_chars = self._count_chars(messages)
        if original_chars <= max_chars:
            return CompressionResult(
                messages=list(messages),
                compressed=False,
                original_chars=original_chars,
                compressed_chars=original_chars,
            )

        system_messages = [msg for msg in messages if msg.get("role") == "system"]
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

    def _summarize(self, messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for index, message in enumerate(messages, start=1):
            role = str(message.get("role", "unknown"))
            content = str(message.get("content", ""))
            if not content:
                continue
            one_line = " ".join(content.split())
            if len(one_line) > 300:
                one_line = one_line[:297] + "..."
            lines.append(f"{index}. {role}: {one_line}")
        summary = "\n".join(lines)
        if len(summary) > self.max_summary_chars:
            return summary[: self.max_summary_chars - 4] + "\n..."
        return summary

    @staticmethod
    def _count_chars(messages: list[dict[str, Any]]) -> int:
        return sum(len(str(message.get("content", ""))) for message in messages)

    @classmethod
    def _force_fit(cls, messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
        fitted: list[dict[str, Any]] = []
        remaining = max(0, max_chars)
        for message in messages:
            if remaining <= 0:
                break
            content = str(message.get("content", ""))
            if len(content) > remaining:
                content = content[: max(0, remaining - 4)] + "\n..."
            cloned = dict(message)
            cloned["content"] = content
            fitted.append(cloned)
            remaining -= len(content)
        return fitted
