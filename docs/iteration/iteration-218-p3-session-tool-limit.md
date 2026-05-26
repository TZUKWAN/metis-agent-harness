---
iteration: 218
date: 2026-05-26
phase: P3 Reliability
status: completed
---

# Iteration 218: Add per-session tool call limit

## Changes
- Added MAX_TOOLS_PER_SESSION=200 to metis/config.py
- AgentLoop now counts total tool calls across all turns
- Blocks with status="blocked" when limit exceeded, preventing runaway agents

## Test Results
- 714 passed, 0 failed, 10 skipped
