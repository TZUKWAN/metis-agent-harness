---
iteration: 220
date: 2026-05-26
phase: P3 Reliability
status: completed
---

# Iteration 220: Move session tool limit to per-profile config

## Changes
- Added max_session_tool_calls field to ModelProfile (default 200)
- Small profile: 150, deep profile: 500, balanced/small_strict: 200
- AgentLoop now uses profile.max_session_tool_calls instead of global config constant
- Removed direct MAX_TOOLS_PER_SESSION import from loop.py

## Test Results
- 723 passed, 0 failed, 10 skipped
