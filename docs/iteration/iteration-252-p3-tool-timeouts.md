---
iteration: 252
date: 2026-05-26
phase: P3 Reliability
status: completed
---

# Iteration 252: Add per-category tool timeouts

## Changes
- Added timeout_seconds field to ToolSpec (default None = use global)
- ToolDispatcher uses per-tool timeout if set, falls back to TOOL_EXECUTION_TIMEOUT
- run_shell gets 120s timeout (was 30s global) since shell commands often take longer
- Reduces unnecessary timeouts on legitimate long-running commands

## Test Results
- 791 passed, 0 failed, 10 skipped
