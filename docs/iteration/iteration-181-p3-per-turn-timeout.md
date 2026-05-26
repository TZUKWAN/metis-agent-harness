---
iteration: 181
date: 2026-05-26
phase: P3 Runtime
status: completed
---

# Iteration 181: Add per-turn timeout to agent loop

## Changes
- Added PER_TURN_TIMEOUT=120 config constant
- Agent loop wraps provider.complete() with asyncio.wait_for(timeout=120s)
- On timeout: logs warning, appends error, continues to next turn
- Prevents single model call from hanging the entire agent loop

## Test Results
- 630 passed, 0 failed, 8 skipped
