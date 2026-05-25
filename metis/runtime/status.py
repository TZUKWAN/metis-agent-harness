"""Canonical runtime statuses."""

from __future__ import annotations

from enum import StrEnum


class RuntimeStatus(StrEnum):
    FINAL = "final"
    DONE = "done"
    BLOCKED = "blocked"
    NEEDS_MORE_WORK = "needs_more_work"
    MAX_TURNS = "max_turns"
    FAILED = "failed"

    @classmethod
    def from_strict_status(cls, status: str) -> "RuntimeStatus":
        if status == "done":
            return cls.FINAL
        if status == "blocked":
            return cls.BLOCKED
        if status == "needs_more_work":
            return cls.NEEDS_MORE_WORK
        return cls.FAILED

    @property
    def step_status(self) -> str:
        if self == RuntimeStatus.FINAL:
            return "done"
        if self == RuntimeStatus.NEEDS_MORE_WORK:
            return "needs_more_work"
        if self == RuntimeStatus.BLOCKED:
            return "blocked"
        return "failed"
