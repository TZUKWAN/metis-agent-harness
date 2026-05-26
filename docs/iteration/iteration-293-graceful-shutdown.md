# Iteration 293: Graceful Shutdown for In-Progress Agent Turns

## Problem
On shutdown, the server immediately cancelled the cleanup task but did not wait for in-progress agent turns. This could cause:
- Truncated responses to clients
- Incomplete session state recording
- Abrupt WebSocket/SSE disconnections

## Solution

1. **Shutdown flag**: `app.state.shutting_down = True` set at the start of shutdown, allowing middleware to reject new requests while existing ones complete.

2. **Graceful wait**: During shutdown, polls the `concurrency_limiter._value` (available slots) vs `max_concurrent`. While slots are occupied (active turns), waits up to `METIS_SHUTDOWN_TIMEOUT` seconds (default 30s) for them to complete.

3. **Logging**: Reports number of active requests during the wait period for operational visibility.

## Changes
- `metis/app/web.py`: Enhanced lifespan shutdown to wait for active agent turns

## Result
787 passed, 0 failed
