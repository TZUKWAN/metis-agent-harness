"""Tool-call parser base types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from metis.runtime.response import ToolCall


class ToolCallParser(ABC):
    @abstractmethod
    def parse(self, raw: Any) -> list[ToolCall]:
        """Parse tool calls from provider-specific raw data."""
