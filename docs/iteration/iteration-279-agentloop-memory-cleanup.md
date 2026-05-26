# Iteration 279: Fix AgentLoop Memory Leak from Session Dictionaries

## Problem
`AgentLoop._SESSION_TOOL_COUNTS` and `_SESSION_TOOL_FAILURES` were class-level dictionaries that accumulated entries indefinitely. In a long-running web service, each unique `session_id` would leave behind orphaned entries, causing memory to grow without bound (OOM risk).

## Solution

1. **Track activity timestamps**: Added `_SESSION_LAST_ACTIVITY` dict recording the last `time.monotonic()` for each active session.

2. **Automatic cleanup on run exit**: Wrapped `run()` body in `try/finally` calling `_cleanup_session_state()`, ensuring cleanup happens on normal return, early return, **and exception paths**.

3. **Stale entry eviction**: Added `_prune_session_state()` that:
   - Removes sessions idle longer than `_SESSION_ACTIVITY_TTL` (3600s)
   - If total tracked sessions exceeds `_MAX_TRACKED_SESSIONS` (1000), evicts oldest by activity time

4. **Explicit cleanup helper**: `_cleanup_session_state()` removes a session from all three dicts atomically.

## Changes
- `metis/runtime/loop.py`:
  - Added `_SESSION_LAST_ACTIVITY`, `_MAX_TRACKED_SESSIONS`, `_SESSION_ACTIVITY_TTL` class constants
  - Added `_cleanup_session_state()` and `_prune_session_state()` static methods
  - `run()` now wrapped in `try/finally` for guaranteed cleanup
  - Calls `_prune_session_state()` at session start

## Tests
- `tests/unit/test_session_memory_cleanup.py`:
  - `test_session_state_cleaned_after_run`
  - `test_session_state_cleaned_on_exception`
  - `test_prune_evicts_stale_sessions`
  - `test_prune_evicts_oldest_when_over_limit`
  - `test_cleanup_session_state_removes_all`

## Result
747 passed, 0 failed
