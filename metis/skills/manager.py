"""Skill model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    content: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)

    def summary(self, max_chars: int = 800) -> str:
        text = f"{self.name}: {self.description}\nTriggers: {', '.join(self.triggers)}\n{self.content}"
        return text if len(text) <= max_chars else text[: max_chars - 4] + "\n..."
