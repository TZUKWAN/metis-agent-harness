"""Context budget engine with token-aware compression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metis.context.compressor import CompressionResult, SimpleContextCompressor
from metis.context.tokenizer import CompositeTokenEstimator, TokenEstimator
from metis.runtime.budgets import BudgetConfig


@dataclass(frozen=True)
class ContextBuildResult:
    messages: list[dict[str, Any]]
    compressed: bool
    original_chars: int
    final_chars: int
    max_chars: int
    summary: str = ""
    original_tokens: int = 0
    final_tokens: int = 0
    tool_schema_tokens: int = 0


class ContextEngine:
    """Apply a token-aware budget before provider calls.

    The engine estimates token usage using a language-aware estimator that
    correctly accounts for CJK text density. Tool schemas are also counted
    toward the budget so the limit reflects *actual* provider consumption.
    """

    def __init__(
        self,
        *,
        budget: BudgetConfig | None = None,
        compressor: SimpleContextCompressor | None = None,
        chars_per_token: int = 4,
        override_max_context_tokens: int | None = None,
        estimator: TokenEstimator | None = None,
    ) -> None:
        self.budget = budget or BudgetConfig.for_profile("small")
        self.compressor = compressor or SimpleContextCompressor(
            max_tool_result_chars=self.budget.per_tool_chars,
        )
        self.chars_per_token = chars_per_token
        self.override_max_context_tokens = override_max_context_tokens
        self.estimator = estimator or CompositeTokenEstimator()

    @property
    def max_context_tokens(self) -> int:
        return self.override_max_context_tokens or self.budget.model_context_tokens

    @property
    def max_chars(self) -> int:
        # Legacy char-based budget for backward compatibility with compressor
        tokens = self.max_context_tokens
        return int(tokens * self.chars_per_token * self.budget.context_threshold)

    @property
    def max_total_tokens(self) -> int:
        """Maximum tokens allowed including a safety margin."""
        return int(self.max_context_tokens * self.budget.context_threshold)

    def build(
        self,
        messages: list[dict[str, Any]],
        *,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> ContextBuildResult:
        """Build context within token budget.

        Args:
            messages: Conversation messages to compress if needed.
            tool_schemas: Optional tool JSON schemas to count toward budget.
        """
        original_chars = self._count_chars(messages)
        original_tokens = self.estimator.estimate_total(messages, tool_schemas)
        tool_schema_tokens = (
            self.estimator.estimate_tool_schemas(tool_schemas) if tool_schemas else 0
        )

        max_tokens = self.max_total_tokens

        if original_tokens <= max_tokens:
            return ContextBuildResult(
                messages=list(messages),
                compressed=False,
                original_chars=original_chars,
                final_chars=original_chars,
                max_chars=self.max_chars,
                original_tokens=original_tokens,
                final_tokens=original_tokens,
                tool_schema_tokens=tool_schema_tokens,
            )

        # Token-over-budget: translate token budget back to approximate char budget
        # for the compressor, accounting for tool schema overhead.
        token_overhead = tool_schema_tokens
        available_message_tokens = max(0, max_tokens - token_overhead)
        # Convert token budget to char budget using current text density
        if original_tokens > 0:
            density = original_chars / original_tokens
        else:
            density = self.chars_per_token
        max_message_chars = int(available_message_tokens * density)
        max_message_chars = max(1000, max_message_chars)

        compressed: CompressionResult = self.compressor.compress(
            messages, max_chars=max_message_chars
        )
        final_tokens = self.estimator.estimate_total(compressed.messages, tool_schemas)

        return ContextBuildResult(
            messages=compressed.messages,
            compressed=compressed.compressed,
            original_chars=compressed.original_chars,
            final_chars=compressed.compressed_chars,
            max_chars=self.max_chars,
            summary=compressed.summary,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            tool_schema_tokens=tool_schema_tokens,
        )

    @staticmethod
    def _count_chars(messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += len(str(message.get("content", "")))
            total += len(str(message.get("reasoning_content", "")))
        return total
