# Iteration 275: Adaptive Per-Turn Timeout Based on Model Capabilities

## Problem
`PER_TURN_TIMEOUT` was fixed at 120 seconds regardless of model capabilities. Large-output models (e.g., glm-4.9 with 16K max output) could hit timeouts on long generations, while small models unnecessarily waited the full duration.

## Solution
Scale per-turn timeout dynamically based on the provider's detected `max_output_tokens`:

- **Formula**: `max(120, min(600, 90 + (max_output_tokens / 1000) * 25))`
  - Base 90s for connection/processing overhead
  - +25s per 1K output tokens (assuming ~40 tokens/s generation rate)
  - Lower bound: 120s (existing default)
  - Upper bound: 600s (`MAX_TIMEOUT`)

- **Examples**:
  - glm-4 (4K): 190s
  - glm-4.7-flash (8K): 290s
  - glm-4.9 (16K): 490s
  - Undetected model: 120s (fallback)

## Changes
- `metis/runtime/loop.py`:
  - Added `_compute_per_turn_timeout()` static method
  - In `__init__`: probe provider capabilities for `max_output_tokens` and compute `self.per_turn_timeout`
  - Replaced all hardcoded `PER_TURN_TIMEOUT` references with `self.per_turn_timeout`
  - Added `per_turn_timeout` to `model.request` trace event attributes

## Tests
- `tests/unit/test_adaptive_timeout.py`:
  - `test_timeout_defaults_when_no_capabilities`
  - `test_timeout_for_4k_model`
  - `test_timeout_for_8k_model`
  - `test_timeout_for_16k_model`
  - `test_timeout_clamped_at_maximum`
  - `test_timeout_clamped_at_minimum`
  - `test_trace_event_includes_timeout`

## Result
720 passed, 0 failed
