# Iteration 272: Auto-Set max_tokens in Provider Requests

## Problem
Provider requests did not include `max_tokens`, allowing models (especially 8B) to generate unnecessarily long outputs. This wasted tokens, increased latency, and could overflow the context window with verbose responses.

## Solution
Automatically set `max_tokens` in API requests based on detected model capabilities:

1. **Environment override**: `METIS_PROVIDER_MAX_TOKENS` always takes precedence
2. **Explicit parameter preserved**: If caller passes `max_tokens`, it is not overridden
3. **Auto-detection**: Uses `capabilities().max_output_tokens` when no explicit value given
4. **Skip for unknown models**: If detection returns 0, `max_tokens` is omitted

## Changes
- `metis/providers/openai_compat.py`:
  - After payload construction, check and set `max_tokens` from env var, explicit param, or detected capability

## Tests
- `tests/unit/test_provider_max_tokens.py`:
  - `test_auto_max_tokens_from_detected_capabilities`
  - `test_explicit_max_tokens_preserved`
  - `test_env_var_overrides_auto`
  - `test_zero_detected_skips_max_tokens`

## Result
946 passed, 10 skipped
