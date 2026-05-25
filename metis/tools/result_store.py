"""Persistence for oversized tool results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from metis.runtime.budgets import BudgetConfig
from metis.security.redaction import redact_secrets

PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"


@dataclass
class PersistedToolResult:
    content: str
    persisted: bool
    path: str | None = None
    original_size: int = 0
    checksum: str = ""


class ToolResultStore:
    def __init__(self, workspace: str | Path = ".", budget: BudgetConfig | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.budget = budget or BudgetConfig.for_profile("small")
        self.output_dir = self.workspace / ".metis" / "tool-results"

    def maybe_persist(
        self,
        *,
        content: str,
        tool_name: str,
        tool_call_id: str,
        threshold: int | None = None,
    ) -> PersistedToolResult:
        limit = threshold if threshold is not None else self.budget.per_tool_chars
        content = redact_secrets(content)
        if len(content) <= limit:
            return PersistedToolResult(content=content, persisted=False, original_size=len(content), checksum=self._sha(content))

        file_name = f"{tool_call_id or tool_name}.txt"
        path = self.output_dir / file_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        preview = self.generate_preview(content, self.budget.preview_chars)
        persisted_content = self._build_persisted_message(
            preview=preview,
            original_size=len(content),
            file_path=str(path),
        )
        return PersistedToolResult(
            content=persisted_content,
            persisted=True,
            path=str(path),
            original_size=len(content),
            checksum=self._sha(content),
        )

    @staticmethod
    def generate_preview(content: str, max_chars: int) -> str:
        if len(content) <= max_chars:
            return content
        chunk = content[:max_chars]
        last_newline = chunk.rfind("\n")
        if last_newline > max_chars // 2:
            chunk = chunk[: last_newline + 1]
        return chunk + "\n..."

    @staticmethod
    def _build_persisted_message(*, preview: str, original_size: int, file_path: str) -> str:
        return (
            f"{PERSISTED_OUTPUT_TAG}\n"
            f"This tool result was too large ({original_size} characters).\n"
            f"Full output saved to: {file_path}\n"
            "Use read_file with offsets or inspect the file directly for more detail.\n\n"
            f"Preview:\n{preview}\n"
            f"{PERSISTED_OUTPUT_CLOSING_TAG}"
        )

    @staticmethod
    def _sha(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
