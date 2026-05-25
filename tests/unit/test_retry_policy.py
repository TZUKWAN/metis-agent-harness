import random

from metis.recovery.classifier import ErrorCategory
from metis.recovery.retry import RetryPolicy


def test_retry_policy_limits_attempts_and_jitters_delay():
    policy = RetryPolicy(max_retries=2, base_delay=1.0, max_delay=3.0)

    assert policy.should_retry(ErrorCategory.NETWORK, 0) is True
    assert policy.should_retry(ErrorCategory.NETWORK, 2) is False
    assert policy.should_retry(ErrorCategory.AUTH, 0) is False
    delay = policy.delay_for(1, rng=random.Random(1))
    assert 2.0 <= delay <= 2.5
    assert policy.delay_for(5, rng=random.Random(1)) <= 3.0
