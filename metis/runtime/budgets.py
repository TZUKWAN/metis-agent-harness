"""Runtime budget presets for context and tool results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetConfig:
    per_tool_chars: int = 8000
    per_turn_chars: int = 30000
    preview_chars: int = 2000
    model_context_tokens: int = 32768
    context_threshold: float = 0.65

    @classmethod
    def for_profile(cls, profile: str) -> "BudgetConfig":
        if profile == "small":
            return cls(
                per_tool_chars=4000,
                per_turn_chars=20000,
                preview_chars=1200,
                model_context_tokens=128000,
                context_threshold=0.50,
            )
        if profile == "deep":
            return cls(
                per_tool_chars=24000,
                per_turn_chars=120000,
                preview_chars=8000,
                model_context_tokens=128000,
                context_threshold=0.75,
            )
        return cls()
