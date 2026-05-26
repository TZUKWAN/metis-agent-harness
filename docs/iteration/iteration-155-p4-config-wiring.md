---
iteration: 155
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 155: Config wiring - eliminate hardcoded defaults

## Changes
- `metis/tools/builtin.py`: Removed local MAX_CONTENT_LENGTH and MAX_TIMEOUT, now imports from metis.config
- `metis/runtime/response.py`: AgentRunRequest.max_turns now uses DEFAULT_MAX_TURNS from config
- All hardcoded defaults now traceable to single source (metis/config.py)

## Test Results
- 485 passed, 0 failed, 6 skipped
