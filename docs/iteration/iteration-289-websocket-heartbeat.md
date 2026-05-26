# Iteration 289: WebSocket Heartbeat for chat_stream

## Problem
The WebSocket `/api/v1/chat/stream` endpoint had no heartbeat during long-running agent turns. Reverse proxies and load balancers (Nginx, Cloudflare) typically close idle WebSocket connections after 30-60 seconds, causing silent disconnections during long agent responses.

## Solution

1. **Heartbeat task**: During each `run_agent_turn()` execution, a background `asyncio.Task` sends `{"type": "ping"}` every 15 seconds:
   - Keeps the connection alive through proxies
   - Detects broken connections early via send failure

2. **Lifecycle management**: Heartbeat task is created before `run_agent_turn` and cancelled in a `finally` block when the turn completes:
   - Fast turns complete before the first heartbeat fires (15s interval)
   - Long turns receive periodic pings
   - No heartbeat leaks after turn completion

## Changes
- `metis/app/web.py`: Added heartbeat coroutine in `chat_stream` WebSocket handler
- `tests/unit/test_websocket_heartbeat.py`: 2 tests for heartbeat during long turn and no heartbeat during fast turn

## Tests
- `test_heartbeat_sends_ping_during_long_turn`
- `test_no_heartbeat_after_turn_completes`

## Result
774 passed, 0 failed
