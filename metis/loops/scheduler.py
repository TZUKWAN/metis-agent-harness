"""Simple schedule parsing for loop triggers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


EVERY_RE = re.compile(r"^every\s+(\d+)\s+minutes?$", re.I)
DAILY_RE = re.compile(r"^daily\s+([01]\d|2[0-3]):([0-5]\d)$", re.I)


@dataclass(frozen=True)
class Schedule:
    expression: str
    kind: str
    minutes: int | None = None
    hour: int | None = None
    minute: int | None = None

    def next_after(self, now: datetime) -> datetime:
        if self.kind == "every":
            return now + timedelta(minutes=int(self.minutes or 0))
        candidate = now.replace(hour=int(self.hour or 0), minute=int(self.minute or 0), second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate


class Scheduler:
    def parse(self, expression: str) -> Schedule:
        expression = expression.strip()
        every = EVERY_RE.match(expression)
        if every:
            minutes = int(every.group(1))
            if minutes <= 0:
                raise ValueError("Schedule interval must be positive")
            return Schedule(expression=expression, kind="every", minutes=minutes)
        daily = DAILY_RE.match(expression)
        if daily:
            return Schedule(expression=expression, kind="daily", hour=int(daily.group(1)), minute=int(daily.group(2)))
        raise ValueError(f"Unsupported schedule expression: {expression}")


@dataclass(frozen=True)
class ScheduledLoop:
    id: str
    loop_id: str
    expression: str
    next_run_at: str
    status: str = "active"


class SchedulerStore:
    def __init__(self, state, scheduler: Scheduler | None = None) -> None:
        self.state = state
        self.scheduler = scheduler or Scheduler()

    def create(self, *, loop_id: str, expression: str, now: datetime) -> ScheduledLoop:
        schedule = self.scheduler.parse(expression)
        next_run_at = schedule.next_after(now).isoformat()
        schedule_id = self.state.create_schedule(loop_id=loop_id, expression=expression, next_run_at=next_run_at)
        return self.get(schedule_id)

    def get(self, schedule_id: str) -> ScheduledLoop:
        row = self.state.get_schedule(schedule_id)
        if row is None:
            raise KeyError(f"Unknown schedule: {schedule_id}")
        return ScheduledLoop(
            id=row["id"],
            loop_id=row["loop_id"],
            expression=row["expression"],
            next_run_at=row["next_run_at"],
            status=row["status"],
        )

    def list(self, loop_id: str | None = None) -> list[ScheduledLoop]:
        return [
            ScheduledLoop(
                id=row["id"],
                loop_id=row["loop_id"],
                expression=row["expression"],
                next_run_at=row["next_run_at"],
                status=row["status"],
            )
            for row in self.state.list_schedules(loop_id)
        ]

    def update_next_run(self, schedule_id: str, now: datetime) -> ScheduledLoop:
        current = self.get(schedule_id)
        schedule = self.scheduler.parse(current.expression)
        next_run_at = schedule.next_after(now).isoformat()
        self.state.update_schedule_next_run(schedule_id, next_run_at)
        return self.get(schedule_id)
