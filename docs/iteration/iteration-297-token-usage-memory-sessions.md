# Iteration 297: Token Usage for In-Memory Sessions

## Problem
`/sessions/{id}/usage` returned zeros for in-memory sessions because token tracking only worked with a persistent state store. The `AgentRunResult.usage` data was discarded.

## Solution

1. **Usage accumulation in `_record_session`**: Each agent turn's `usage` dict is now accumulated into the session's `usage` field (prompt_tokens, completion_tokens, total_tokens, api_calls).

2. **Session initialization**: New sessions include a `usage` dict initialized to zeros.

3. **Usage endpoint**: `/sessions/{id}/usage` now checks in-memory sessions first, falling back to state store.

## Changes
- `metis/app/web.py`: `_record_session` accumulates token usage, `session_usage` checks memory first

## Result
791 passed, 0 failed
