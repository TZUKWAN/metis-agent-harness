from datetime import datetime

import pytest

from metis.loops.scheduler import Scheduler


def test_scheduler_parses_every_minutes():
    schedule = Scheduler().parse("every 15 minutes")

    assert schedule.kind == "every"
    assert schedule.next_after(datetime(2026, 1, 1, 10, 0)) == datetime(2026, 1, 1, 10, 15)


def test_scheduler_parses_daily_time():
    schedule = Scheduler().parse("daily 09:30")

    assert schedule.kind == "daily"
    assert schedule.next_after(datetime(2026, 1, 1, 8, 0)) == datetime(2026, 1, 1, 9, 30)
    assert schedule.next_after(datetime(2026, 1, 1, 10, 0)) == datetime(2026, 1, 2, 9, 30)


def test_scheduler_rejects_unsupported_expression():
    with pytest.raises(ValueError):
        Scheduler().parse("weekly monday")
