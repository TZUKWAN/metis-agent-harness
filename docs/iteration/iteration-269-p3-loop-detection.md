# Iteration 269: Detect and Break Model Response Loops

## Problem
Small models (8B) can get stuck in loops, repeatedly requesting the same tool calls or returning the same text responses across multiple turns. This wastes tokens, API calls, and user time.

## Solution
Add turn-level response loop detection that tracks assistant response signatures:

1. **Signature generation** (`_turn_signature`): Compact hash of tool calls (names + args) or text content
2. **Loop detection** (`_detect_response_loop`): If the same signature appears for 3 consecutive turns, trigger
3. **Early termination**: Return `blocked` status with guidance to try a different approach
4. **Trace event**: Record `agent.loop_detected` for observability

## Changes
- `metis/runtime/loop.py`:
  - Added `turn_signatures` tracking in `run()`
  - Added `_turn_signature()` static method
  - Added `_detect_response_loop()` static method
  - Loop check inserted after `one_tool_call_per_turn` truncation, before `max_tool_calls_per_turn` check

## Tests
- `tests/unit/test_loop_detection.py`:
  - `test_loop_detection_triggers_on_repeated_tool_calls`
  - `test_detect_response_loop_on_text_signatures`
  - `test_loop_detection_does_not_trigger_on_two_repeats`
  - `test_loop_detection_does_not_trigger_on_varied_responses`
  - `test_turn_signature_tools`
  - `test_turn_signature_text`
  - `test_detect_response_loop_true`
  - `test_detect_response_loop_false`

## Integration
- Updated `test_agent_loop_pre_dispatch_blocks_repeated_call_after_retry_budget_exhausted` to account for loop detection triggering before retry budget pre-dispatch block on identical repeated calls

## Result
929 passed, 10 skipped
