# Iteration 274: Enrich Trace Events with Request Metadata

## Problem
The `model.request` trace event lacked operational metadata needed for debugging context budget issues, model selection, and compression behavior in production.

## Solution
Enrich the `model.request` trace event with detailed request metadata:

1. **`model`**: Provider's model identifier (e.g., "test-model-v1", "glm-4.7-flash")
2. **`estimated_tokens`**: Character count divided by `chars_per_token` estimate
3. **`max_chars_budget`**: The context budget limit from `ContextEngine`
4. **`compression_ratio`**: `original_chars / final_chars` when compression occurred, `1.0` otherwise
5. **`message_count`**: Number of messages sent to the model
6. **`tool_count`**: Number of tool schemas available
7. **`compressed`**: Whether context compression was applied

## Changes
- `metis/runtime/loop.py`:
  - Extended `model.request` trace event `attributes` dict in `run()` method
  - Calculated `est_tokens` from `context_result.final_chars // chars_per_token`
  - Added `compression_ratio` using `original_chars / final_chars`

## Tests
- `tests/unit/test_trace_event_enrichment.py`:
  - `test_model_request_trace_includes_metadata`: Verifies all fields present
  - `test_compression_ratio_recorded_when_compressed`: Verifies ratio > 1.0 on compressed long messages

## Result
713 unit tests collected, trace enrichment tests pass
