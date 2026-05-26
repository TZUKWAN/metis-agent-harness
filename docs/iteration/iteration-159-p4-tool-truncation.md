---
iteration: 159
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 159: Smart tool call truncation for 8B models

## Problem
GLM-4.7-Flash with `small` profile (one_tool_call_per_turn=True) would return multiple
tool calls at once, causing the loop to BLOCK instead of executing. Multi-tool tasks
like "explore project and create document" always failed.

## Solution
Changed `one_tool_call_per_turn` enforcement from hard BLOCK to smart truncation:
- When model returns multiple calls but profile limits to 1, keep only the first call
- Log a trace event (tool.truncate) for observability
- Continue execution instead of blocking
- Hard limit (max_tool_calls_per_turn) still blocks when truly exceeded

## E2E Results
- GLM multi-tool explore+report: PASS (was blocked before)
- GLM flowchart generation: PASS
- GLM read_file (small profile): PASS
- GLM write_file (small profile): PASS

## Test Results
- 512 passed, 0 failed, 3 skipped
