# Iteration 273: Context Compression Priority Scoring

## Problem
Context compression's `_force_fit` method indiscriminately truncated messages in order when space ran out. This could drop critical error feedback or user instructions while preserving old, low-value read results.

## Solution
Add importance scoring to messages so `_force_fit` drops lowest-score messages first:

1. **Scoring** (`_score_message`):
   - system: 100 (always preserved)
   - critical tool results (errors): 90
   - user messages: 80
   - recent tool results (last 4): 75
   - assistant with tool_calls: 70
   - assistant text: 50
   - older tool results: 40
   - unknown roles: 30

2. **Smart eviction**: `_force_fit` sorts non-system messages by score (descending), allocates space to highest first, drops lowest completely before truncating anything

3. **Order preserved**: After selection, messages are re-sorted by original index to maintain conversation flow

## Changes
- `metis/context/compressor.py`:
  - Added `_score_message()` static method
  - Rewrote `_force_fit()` to use score-based eviction

## Tests
- `tests/unit/test_compressor_scoring.py`:
  - `test_system_always_highest_score`
  - `test_user_high_score`
  - `test_assistant_with_tools_higher_than_text`
  - `test_critical_tool_result_high_score`
  - `test_recent_tool_higher_than_old`
  - `test_force_fit_preserves_system_and_high_priority`
  - `test_force_fit_drops_lowest_score_first`

## Result
953 passed, 10 skipped
