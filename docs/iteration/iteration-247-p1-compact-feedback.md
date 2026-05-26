---
iteration: 247
date: 2026-05-26
phase: P1 Core Features
status: completed
---

# Iteration 247: Add compact error messages for 8B models

## Changes
- Added _compact_feedback() static method to AgentLoop
- Truncates JSON tool feedback to 4000 chars max
- Intelligently truncates long error, stderr, stdout, and result fields to 500 chars
- Applied to both cached and fresh tool result feedback paths
- Reduces context bloat from verbose tool outputs

## Test Results
- 791 passed, 0 failed, 10 skipped
