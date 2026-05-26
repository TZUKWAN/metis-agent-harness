# Iteration 280: FastAPI Global Request Timeout Middleware

## Problem
FastAPI had no request-level timeout. If a model API call hung or a client kept a connection open, the request would consume a worker thread indefinitely, potentially exhausting the connection pool and causing service unavailability.

## Solution
Added a `request_timeout` middleware that wraps `call_next` in `asyncio.wait_for`:

- **Non-chat endpoints**: 30-second timeout (health, config, metrics, etc.)
- **Chat endpoints**: 600-second timeout (allows long-running agent sessions)
- Returns HTTP 504 with a descriptive JSON error on timeout

## Changes
- `metis/app/web.py`:
  - Added `request_timeout` middleware before `auth_and_rate_limit`

## Tests
- `tests/unit/test_web_timeout.py`:
  - `test_fast_request_succeeds`: Verifies health endpoint still responds quickly

## Result
748 passed, 0 failed
