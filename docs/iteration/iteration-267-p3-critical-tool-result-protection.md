# Iteration 254: Protect Critical Tool Results in Context Compression

## Problem
When context compression trims tool results, it treats all results equally. For small models (8B), losing error feedback or state-change confirmations mid-conversation severely degrades self-correction ability.

## Solution
Add smart protection for critical tool results during context compression:

1. **Detection** (`_is_critical_tool_result`): Identify messages containing errors, failures, blocked status, or write confirmations
2. **Larger trim budget**: Critical results get 3x the normal `max_tool_result_chars` limit before trimming
3. **Summary annotation**: Critical results are marked with `[CRITICAL]` in compression summaries so the model knows they were important

## Changes
- `metis/context/compressor.py`:
  - Added `_is_critical_tool_result()` static method
  - Modified `_trim_large_tool_results()` to use 3x limit for critical messages
  - Modified `_summarize()` to prepend `[CRITICAL] ` to critical tool lines

## Tests
- `tests/unit/test_context_trim.py`:
  - `test_critical_tool_result_with_error_gets_larger_limit`
  - `test_critical_tool_result_with_status_blocked`
  - `test_critical_tool_result_with_write_confirmation`
  - `test_non_critical_tool_result_still_trimmed`
  - `test_is_critical_tool_result_detects_error`
  - `test_summary_marks_critical_results`

## Result
914 passed, 10 skipped
