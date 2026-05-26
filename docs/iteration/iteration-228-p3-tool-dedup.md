---
iteration: 228
date: 2026-05-26
phase: P3 Reliability
status: completed
---

# Iteration 228: Add tool call deduplication

## Changes
- AgentLoop now caches successful tool results keyed by (name, sorted_args)
- Repeated identical calls return cached result with from_cache=True metadata
- State recording still happens for eval tracking (measures intent, not execution)
- Failed tool calls are NOT cached (retry is valid)

## Test Results
- 767 passed, 0 failed, 10 skipped
