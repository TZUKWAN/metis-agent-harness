"""Tests for web API rate limiting."""

from __future__ import annotations

import asyncio
import time

import pytest

from metis.app.web import _check_rate_limit, _check_session_rate_limit, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW


@pytest.fixture(autouse=True)
def _clear_rate_limit_stores():
    from metis.app.web import _RATE_LIMIT_STORE, _RATE_LIMIT_SESSION_STORE
    _RATE_LIMIT_STORE.clear()
    _RATE_LIMIT_SESSION_STORE.clear()


async def test_rate_limit_allows_under_limit():
    for _ in range(RATE_LIMIT_MAX - 1):
        await _check_rate_limit("127.0.0.1")


async def test_rate_limit_blocks_over_limit():
    from fastapi import HTTPException
    for _ in range(RATE_LIMIT_MAX):
        await _check_rate_limit("10.0.0.1")
    with pytest.raises(HTTPException) as exc:
        await _check_rate_limit("10.0.0.1")
    assert exc.value.status_code == 429


async def test_rate_limit_different_ips_independent():
    for _ in range(RATE_LIMIT_MAX):
        await _check_rate_limit("ip_a")
    await _check_rate_limit("ip_b")


async def test_session_rate_limit_blocks_over_limit():
    from fastapi import HTTPException
    for _ in range(10):
        await _check_session_rate_limit("sess_1")
    with pytest.raises(HTTPException) as exc:
        await _check_session_rate_limit("sess_1")
    assert exc.value.status_code == 429


async def test_session_rate_limit_different_sessions():
    for _ in range(10):
        await _check_session_rate_limit("sess_a")
    await _check_session_rate_limit("sess_b")
