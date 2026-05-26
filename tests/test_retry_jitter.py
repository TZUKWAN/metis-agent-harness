"""Tests for retry delay jitter in provider."""

from metis.providers.openai_compat import _retry_delay_seconds


def test_retry_delay_with_jitter_exceeds_base():
    base = 2.0
    delay = _retry_delay_seconds(None, 1, base)
    assert delay >= base
    assert delay <= 30.0


def test_retry_delay_exponential_backoff():
    delays = [_retry_delay_seconds(None, i, 2.0) for i in range(1, 5)]
    for i in range(1, len(delays)):
        assert delays[i] >= delays[i - 1] * 0.8


def test_retry_delay_capped_at_30():
    delay = _retry_delay_seconds(None, 10, 100.0)
    assert delay <= 30.0


def test_retry_delay_respects_retry_after_header():
    import httpx

    resp = httpx.Response(429, headers={"retry-after": "5"})
    delay = _retry_delay_seconds(resp, 1, 2.0)
    assert delay == 5.0


def test_retry_delay_retry_after_capped_at_30():
    import httpx

    resp = httpx.Response(429, headers={"retry-after": "60"})
    delay = _retry_delay_seconds(resp, 1, 2.0)
    assert delay == 30.0
