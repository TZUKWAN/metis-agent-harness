"""Context budget engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metis.context.compressor import CompressionResult, SimpleContextCompressor
from metis.runtime.budgets import BudgetConfig


@dataclass(frozen=True)
class ContextBuildResult:
    messages: list[dict[str, Any]]
    compressed: bool
    original_chars: int
    final_chars: int
    max_chars: int
    summary: str = ""


class ContextEngine:
    """Apply a deterministic character budget before provider calls."""

    def __init__(
        self,
        *,
        budget: BudgetConfig | None = None,
        compressor: SimpleContextCompressor | None = None,
        chars_per_token: int = 4,
        override_max_context_tokens: int | None = None,
    ) -> None:
        self.budget = budget or BudgetConfig.for_profile("small")
        self.compressor = compressor or SimpleContextCompressor()
        self.chars_per_token = chars_per_token
        self.override_max_context_tokens = override_max_context_tokens

    @property
    def max_chars(self) -> int:
        tokens = self.override_max_context_tokens or self.budget.model_context_tokens
        return int(tokens * self.chars_per_token * self.budget.context_threshold)

    def build(self, messages: list[dict[str, Any]]) -> ContextBuildResult:
        original_chars = self._count_chars(messages)
        limit = self.max_chars
        if original_chars <= limit:
            return ContextBuildResult(
                messages=list(messages),
                compressed=False,
                original_chars=original_chars,
                final_chars=original_chars,
                max_chars=limit,
            )

        compressed: CompressionResult = self.compressor.compress(messages, max_chars=limit)
        return ContextBuildResult(
            messages=compressed.messages,
            compressed=compressed.compressed,
            original_chars=compressed.original_chars,
            final_chars=compressed.compressed_chars,
            max_chars=limit,
            summary=compressed.summary,
        )

    @staticmethod
    def _count_chars(messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += len(str(message.get("content", "")))
            total += len(str(message.get("reasoning_content", "")))
        return total
