import pytest

from metis.recovery.manager import RecoveryManager
from metis.recovery.retry import RetryPolicy


@pytest.mark.asyncio
async def test_recovery_manager_retries_network_error():
    manager = RecoveryManager(retry_policy=RetryPolicy(max_retries=2, base_delay=0, max_delay=0))
    calls = {"count": 0}

    async def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("network timeout")
        return "ok"

    assert await manager.execute_with_recovery(flaky) == "ok"
    assert calls["count"] == 2


def test_recovery_manager_does_not_retry_auth_error():
    manager = RecoveryManager()

    assert manager.should_retry("401 invalid api key", 0) is False
