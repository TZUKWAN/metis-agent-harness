"""Async loop manager."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from metis.events.hooks import HookBus


@dataclass(frozen=True)
class LoopSpec:
    id: str
    session_id: str
    prompt: str
    interval_seconds: float
    max_iterations: int
    status: str = "created"
    last_run_at: str | None = None
    iterations: int = 0
    consecutive_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "LoopSpec":
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            prompt=row["prompt"],
            interval_seconds=float(row["interval_seconds"]),
            max_iterations=int(row["max_iterations"]),
            status=row["status"],
            last_run_at=row.get("last_run_at"),
            iterations=int(row.get("iterations", 0)),
            consecutive_failures=int(row.get("consecutive_failures", 0)),
            metadata=row.get("metadata", {}),
        )


class LoopManager:
    def __init__(
        self,
        *,
        state,
        execution_controller=None,
        hooks: HookBus | None = None,
        max_consecutive_failures: int = 3,
    ) -> None:
        self.state = state
        self.execution_controller = execution_controller
        self.hooks = hooks or HookBus()
        self.max_consecutive_failures = max_consecutive_failures
        self._tasks: dict[str, asyncio.Task] = {}

    def create(self, *, session_id: str, prompt: str, interval_seconds: float, max_iterations: int) -> LoopSpec:
        loop_id = self.state.create_loop(
            session_id,
            prompt,
            interval_seconds=interval_seconds,
            max_iterations=max_iterations,
        )
        return self.get(loop_id)

    def get(self, loop_id: str) -> LoopSpec:
        row = self.state.get_loop(loop_id)
        if row is None:
            raise KeyError(f"Unknown loop: {loop_id}")
        return LoopSpec.from_row(row)

    def list(self, session_id: str | None = None) -> list[LoopSpec]:
        return [LoopSpec.from_row(row) for row in self.state.list_loops(session_id)]

    def start(self, loop_id: str) -> None:
        if loop_id in self._tasks and not self._tasks[loop_id].done():
            return
        self.state.update_loop_status(loop_id, "running")
        self._tasks[loop_id] = asyncio.create_task(self._run(loop_id))

    def pause(self, loop_id: str) -> None:
        self.state.update_loop_status(loop_id, "paused")

    def resume(self, loop_id: str) -> None:
        self.start(loop_id)

    def stop(self, loop_id: str) -> None:
        self.state.update_loop_status(loop_id, "stopped")
        task = self._tasks.get(loop_id)
        if task and not task.done():
            task.cancel()

    async def wait(self, loop_id: str) -> None:
        task = self._tasks.get(loop_id)
        if task is None:
            return
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _run(self, loop_id: str) -> None:
        while True:
            spec = self.get(loop_id)
            if spec.status not in {"running"}:
                return
            if spec.iterations >= spec.max_iterations:
                self.state.update_loop_status(loop_id, "complete")
                await self.hooks.emit_async("loop.complete", {"loop_id": loop_id})
                return

            failed = False
            try:
                await self.hooks.emit_async("loop.tick", {"loop_id": loop_id, "iteration": spec.iterations + 1})
                if self.execution_controller is not None:
                    await self.execution_controller.run_prompt(session_id=spec.session_id, prompt=spec.prompt)
            except Exception as exc:
                failed = True
                await self.hooks.emit_async("loop.error", {"loop_id": loop_id, "error": str(exc)})
            self.state.record_loop_tick(loop_id, failed=failed)

            updated = self.get(loop_id)
            if updated.consecutive_failures >= self.max_consecutive_failures:
                self.state.update_loop_status(loop_id, "failed")
                return
            if updated.iterations >= updated.max_iterations:
                self.state.update_loop_status(loop_id, "complete")
                await self.hooks.emit_async("loop.complete", {"loop_id": loop_id})
                return
            await asyncio.sleep(updated.interval_seconds)
