"""Deterministic context compression for small-model runs.

Improvements over the original implementation:
1. Protects critical system layers (behavior-rules, task-contract, base-harness)
   from being truncated by _force_fit.
2. Uses configurable per-tool-result limits from BudgetConfig.
3. Handles reasoning_content correctly.
4. Caches critical-tool-result detection to avoid repeated JSON parsing.
5. Richer summary messages that tell the model exactly what was trimmed.
"""

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
    """Keep instructions and recent turns, summarize the middle deterministically.

    Critical system prompt layers (base-harness, task-contract, behavior-rules,
    app-system, app-developer) are NEVER truncated — they are protected as
    first-class context citizens.
    """

    # System layer types that must never be truncated
    PROTECTED_LAYER_TYPES: frozenset[str] = frozenset({
        "base-harness",
        "task-contract",
        "behavior-rules",
        "app-system",
        "app-developer",
    })

    def __init__(
        self,
        *,
        max_summary_chars: int = 4000,
        keep_recent: int = 8,
        max_tool_result_chars: int = 8000,
    ) -> None:
        self.max_summary_chars = max_summary_chars
        self.keep_recent = keep_recent
        self.max_tool_result_chars = max_tool_result_chars
        # Cache for _is_critical_tool_result to avoid repeated JSON parsing
        self._critical_cache: dict[int, bool] = {}

    def compress(self, messages: list[dict[str, Any]], *, max_chars: int) -> CompressionResult:
        original_chars = self._count_chars(messages)
        if original_chars <= max_chars:
            return CompressionResult(
                messages=list(messages),
                compressed=False,
                original_chars=original_chars,
                compressed_chars=original_chars,
            )

        # Phase 1: trim oversized individual tool results
        trimmed = self._trim_large_tool_results(messages)
        trimmed_chars = self._count_chars(trimmed)
        if trimmed_chars <= max_chars:
            return CompressionResult(
                messages=trimmed,
                compressed=True,
                original_chars=original_chars,
                compressed_chars=trimmed_chars,
                summary=f"Trimmed {len(messages)} messages (tool results capped at {self.max_tool_result_chars} chars)",
            )

        # Phase 2: separate protected system layers from evictable messages
        protected_system: list[dict[str, Any]] = []
        evictable: list[dict[str, Any]] = []
        for msg in trimmed:
            if msg.get("role") == "system" and self._is_protected_system(msg):
                protected_system.append(msg)
            else:
                evictable.append(msg)

        # Phase 3: keep recent evictable messages, summarize the rest
        recent = evictable[-self.keep_recent:] if self.keep_recent > 0 else []
        middle = evictable[: max(0, len(evictable) - len(recent))]

        # Generate a rich summary of what was compressed
        summary, trimmed_items = self._summarize(middle)
        summary_message = {
            "role": "system",
            "content": (
                "[Context Compression Summary]\n"
                "Earlier conversation and tool outputs were compacted to preserve the working state.\n"
                f"The following {len(trimmed_items)} items were summarized:\n"
                f"{summary}\n\n"
                "Note: Full tool results for recent turns are preserved below. "
                "If you need details from an earlier step, request them explicitly."
            ),
            "metadata": {"metis_context_summary": True, "compressed_items": len(trimmed_items)},
        }

        compressed_messages = protected_system + [summary_message] + recent
        protected_chars = self._count_chars(protected_system)
        summary_chars = self._count_chars([summary_message])
        recent_chars = self._count_chars(recent)

        # Phase 4: if still over budget, drop recent messages one by one
        while (
            protected_chars + summary_chars + recent_chars > max_chars
            and len(recent) > 1
        ):
            recent = recent[1:]
            recent_chars = self._count_chars(recent)
            compressed_messages = protected_system + [summary_message] + recent

        # Phase 5: last resort — force-fit while NEVER touching protected system layers
        if self._count_chars(compressed_messages) > max_chars:
            compressed_messages = self._force_fit_with_protection(
                compressed_messages, protected_system, max_chars
            )

        compressed_chars = self._count_chars(compressed_messages)
        return CompressionResult(
            messages=compressed_messages,
            compressed=True,
            original_chars=original_chars,
            compressed_chars=compressed_chars,
            summary=summary,
        )

    def _is_protected_system(self, message: dict[str, Any]) -> bool:
        """Check if a system message contains a protected prompt layer."""
        content = str(message.get("content", ""))
        # Check for layer type markers in the content
        for layer_type in self.PROTECTED_LAYER_TYPES:
            if f"[{layer_type}" in content or f"[{layer_type.upper()}" in content:
                return True
        # Also check metadata if present
        metadata = message.get("metadata", {})
        if isinstance(metadata, dict):
            layer_type = metadata.get("layer_type", "")
            if layer_type in self.PROTECTED_LAYER_TYPES:
                return True
        return False

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
            summary_line = f"\n... [trimmed {len(content) - limit} chars — request full output if needed]"
            cloned = dict(message)
            cloned["content"] = trimmed + summary_line
            result.append(cloned)
        return result

    def _is_critical_tool_result(self, message: dict[str, Any]) -> bool:
        """Identify tool results that should be preserved for model self-correction."""
        # Use cached result if available
        msg_id = id(message)
        if msg_id in self._critical_cache:
            return self._critical_cache[msg_id]

        content = str(message.get("content", ""))
        status = str(message.get("status", ""))
        is_critical = False

        if status in ("blocked", "failed", "error"):
            is_critical = True
        elif '"error"' in content or '"error_type"' in content:
            is_critical = True
        else:
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    if "error" in data or "error_type" in data:
                        is_critical = True
                    elif data.get("status") in ("blocked", "failed", "error"):
                        is_critical = True
                    elif "written" in data or "created" in data or "deleted" in data:
                        is_critical = True
            except (json.JSONDecodeError, ValueError):
                pass

        self._critical_cache[msg_id] = is_critical
        return is_critical

    def _summarize(self, messages: list[dict[str, Any]]) -> tuple[str, list[str]]:
        lines: list[str] = []
        trimmed_items: list[str] = []
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
                trimmed_items.append(f"tool:{tool_name}")
            else:
                one_line = " ".join(content.split())
                if role == "assistant" and "tool_calls" in message:
                    trimmed_items.append("assistant:tool_calls")
                else:
                    trimmed_items.append(f"{role}:message")
            if len(one_line) > 300:
                one_line = one_line[:297] + "..."
            lines.append(f"  {index}. {role}: {prefix}{one_line}")
        summary = "\n".join(lines)
        if len(summary) > self.max_summary_chars:
            summary = summary[: self.max_summary_chars - 4] + "\n..."
        return summary, trimmed_items

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
            # Check if it's a protected layer (should never reach here in normal flow)
            content = str(message.get("content", ""))
            for layer in SimpleContextCompressor.PROTECTED_LAYER_TYPES:
                if f"[{layer}" in content:
                    return 1000  # Absolute protection
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
            # Use cached critical check if available
            msg_id = id(message)
            # We can't access instance cache here, so do a quick heuristic
            content = str(message.get("content", ""))
            if '"error"' in content or str(message.get("status", "")) in ("blocked", "failed", "error"):
                return 90
            if index >= total - 4:
                return 75
            return 40
        return 30

    def _force_fit_with_protection(
        self,
        messages: list[dict[str, Any]],
        protected_system: list[dict[str, Any]],
        max_chars: int,
    ) -> list[dict[str, Any]]:
        """Force-fit messages into budget while NEVER touching protected system layers."""
        protected_chars = self._count_chars(protected_system)
        remaining = max(0, max_chars - protected_chars)
        total = len(messages)

        # Separate protected from evictable
        evictable_msgs: list[tuple[int, int, dict[str, Any]]] = []
        for idx, msg in enumerate(messages):
            if msg in protected_system:
                continue
            score = self._score_message(msg, idx, total)
            evictable_msgs.append((score, idx, msg))

        # Sort by importance (highest first)
        evictable_msgs.sort(key=lambda x: x[0], reverse=True)

        fitted: list[tuple[int, dict[str, Any]]] = []
        for _score, idx, message in evictable_msgs:
            if remaining <= 0:
                break
            content = str(message.get("content", ""))
            reasoning = str(message.get("reasoning_content", ""))
            combined_len = len(content) + len(reasoning)

            if combined_len > remaining:
                # Trim content first, then reasoning if needed
                if len(content) > remaining * 0.7:
                    content = content[: max(0, int(remaining * 0.7) - 4)] + "\n..."
                remaining_after_content = remaining - len(content)
                if len(reasoning) > remaining_after_content and remaining_after_content > 50:
                    reasoning = reasoning[: max(0, remaining_after_content - 4)] + "\n..."
                elif len(reasoning) > remaining_after_content:
                    reasoning = ""

            cloned = dict(message)
            cloned["content"] = content
            if reasoning:
                cloned["reasoning_content"] = reasoning
            else:
                cloned.pop("reasoning_content", None)
            fitted.append((idx, cloned))
            remaining -= (len(content) + len(reasoning))

        fitted.sort(key=lambda item: item[0])
        return protected_system + [m for _i, m in fitted]
