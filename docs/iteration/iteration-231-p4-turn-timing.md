---
iteration: 231
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 231: Add per-turn timing metrics

## Changes
- Added time.monotonic() timing per turn in AgentLoop
- Emits "turn.timing" trace event with turn_duration_ms
- Emits "turn.complete" hook event with duration, turn number, tool call count

## Test Results
- 777 passed, 0 failed, 10 skipped
