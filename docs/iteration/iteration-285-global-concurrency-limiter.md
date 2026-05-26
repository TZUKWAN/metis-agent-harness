# Iteration 285: Global Concurrency Limiter for Agent Turns

## Problem
No mechanism limited concurrent `run_agent_turn()` executions. Under high load, unlimited concurrency could exhaust memory, provider API quotas, and degrade response quality—especially critical for 8B models like GLM-4.7-Flash.

## Solution

1. **`asyncio.Semaphore` in app.state**: `create_app()` initializes `asyncio.Semaphore(max_concurrent)`:
   - Default: `max(os.cpu_count() * 2, 4)`
   - Override via `METIS_MAX_CONCURRENT` environment variable

2. **All agent turn entry points protected**:
   - `POST /api/v1/chat`
   - `WebSocket /api/v1/chat/stream`
   - `POST /api/v1/chat/sse`
   - Legacy `POST /api/chat`
   - Legacy `POST /api/chat/sse`
   - Each wraps `run_agent_turn()` with `async with app.state.concurrency_limiter:`

3. **Runtime visibility**: `/api/v1/status` now includes `concurrency` block:
   - `max`: configured limit
   - `active`: currently executing turns
   - `available`: free slots

4. **Test isolation fix**: Added autouse fixtures to `test_web_rate_limit.py` and `test_web_timeout.py` to clear global rate limit stores between tests, preventing state pollution from ASGI client requests.

## Changes
- `metis/app/web.py`: Added Semaphore initialization, wrapped all 5 agent turn entry points, enriched `/status`
- `tests/unit/test_concurrency_limiter.py`: 4 tests for default limit, env override, status visibility, and actual blocking behavior
- `tests/unit/test_web_rate_limit.py`: Added autouse fixture to clear stores
- `tests/unit/test_web_timeout.py`: Added autouse fixture to clear stores

## Tests
- `test_default_concurrency_limit`
- `test_env_override_concurrency_limit`
- `test_status_includes_concurrency`
- `test_semaphore_limits_concurrent_requests`

## Result
755 passed, 0 failed
