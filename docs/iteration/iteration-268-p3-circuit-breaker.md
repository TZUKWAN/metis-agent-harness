# Iteration 268: Circuit Breaker for Repeatedly Failing Tools

## Problem
Small models (8B) can get stuck in loops repeatedly calling the same failing tool, wasting turns and tokens. Without an external signal, the model may not realize a tool is fundamentally broken for the current task.

## Solution
Add a per-session circuit breaker that temporarily blocks tool calls after repeated failures:

1. **Tracking** (`_SESSION_TOOL_FAILURES`): Record failure timestamps per (session, tool)
2. **Threshold**: 3 failures within a 5-minute window triggers the breaker
3. **Cooldown**: 1-minute cooldown period where the tool is blocked
4. **Recovery**: After cooldown, the tool becomes available again (but failures are still tracked)
5. **Clear feedback**: Blocked calls return a descriptive error telling the model to try a different approach

## Changes
- `metis/runtime/loop.py`:
  - Added `_SESSION_TOOL_FAILURES`, `_CIRCUIT_BREAKER_THRESHOLD`, `_CIRCUIT_BREAKER_WINDOW`, `_CIRCUIT_BREAKER_COOLDOWN`
  - Added `_check_circuit_breaker()` static method
  - Added `_record_tool_failure()` static method
  - Circuit breaker check inserted in `_dispatch_tool_call()` after rate limit, before actual dispatch
  - Failure recording added after each failed tool result
  - Session cleanup extended to clear failure history

## Tests
- `tests/unit/test_circuit_breaker.py`:
  - `test_circuit_breaker_blocks_after_threshold`
  - `test_circuit_breaker_resets_per_session`
  - `test_circuit_breaker_allows_success`
  - `test_check_circuit_breaker_returns_none_under_threshold`
  - `test_check_circuit_breaker_returns_message_over_threshold`
  - `test_record_tool_failure_prunes_stale_entries`
  - `test_circuit_breaker_cooldown_allows_recovery`

## Result
921 passed, 10 skipped
