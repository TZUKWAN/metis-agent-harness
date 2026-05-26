---
iteration: 229
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 229: Add token usage tracking events

## Changes
- AgentLoop emits "model.token_usage" hook event after each model call with usage data
- Event includes turn_usage (current turn) and cumulative_usage (running total)
- No event emitted when usage is empty

## Test Results
- 769 passed, 0 failed, 10 skipped
