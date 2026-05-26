---
iteration: 196
date: 2026-05-26
phase: P3 Web API
status: completed
---

# Iteration 196: Add session usage API endpoint

## Changes
- Added GET /api/sessions/{session_id}/usage endpoint
- Returns prompt_tokens, completion_tokens, total_tokens, api_calls
- Queries token_usage table from SQLiteStateStore
- Falls back to zeros if no state store configured

## Test Results
- 682 passed, 0 failed, 8 skipped
