# Iteration 298: SSE task.result() Error Handling

## Problem
Both SSE endpoints (v1 and legacy) called `task.result()` without exception handling. If the background `run_agent_turn` task failed (provider timeout, network error), the exception would propagate through the SSE generator, silently disconnecting the client without any error event.

## Solution

1. **try/except around task.result()**: Both `event_stream()` and `event_stream_legacy()` now catch exceptions from `task.result()`:
   - Logs the error server-side
   - Yields an `error` SSE event to the client
   - Returns early instead of crashing

## Changes
- `metis/app/web.py`: Added try/except for `task.result()` in both SSE event generators

## Result
791 passed, 0 failed
