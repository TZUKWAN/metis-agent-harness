# Iteration 281: Web Layer Memory Protection

## Problem
Web layer had three unbounded in-memory stores that would grow indefinitely:
1. `_RATE_LIMIT_STORE` - IP-level rate limit tracking
2. `_RATE_LIMIT_SESSION_STORE` - Session-level rate limit tracking
3. `app.state.sessions` - In-memory session cache

## Solution

1. **Rate limit store pruning**: Added `_prune_rate_limit_store()` and `_prune_session_rate_limit_store()` that:
   - Remove entries with no active timestamps within the window
   - Evict oldest entries when total exceeds `MAX_RATE_LIMIT_ENTRIES` (10,000)

2. **Session store bounds**: Enhanced `_cleanup_stale_sessions()` to:
   - Evict stale sessions by TTL (3600s)
   - Evict oldest sessions when total exceeds `MAX_IN_MEMORY_SESSIONS` (5,000)

3. **Background cleanup task**: Added `_periodic_cleanup()` async task started on app startup:
   - Runs every 5 minutes (300s)
   - Cleans sessions, rate limits, and session rate limits
   - Logs cleanup counts

4. **Inline pruning**: Rate limit checks now call prune before recording, preventing unbounded growth even under high load.

## Changes
- `metis/app/web.py`:
  - Added `MAX_IN_MEMORY_SESSIONS`, `MAX_RATE_LIMIT_ENTRIES` constants
  - Added `_prune_rate_limit_store()`, `_prune_session_rate_limit_store()`
  - Enhanced `_cleanup_stale_sessions()` with overflow eviction
  - Added `_periodic_cleanup()` background task
  - Added `@app.on_event("startup")` handler

## Tests
- `tests/unit/test_web_timeout.py`: Verifies app still starts correctly
- Implicitly covered by existing web integration tests

## Result
748 passed, 0 failed
