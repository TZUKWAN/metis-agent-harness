# Iteration 271: Dynamic Context Budget from Detected Model Capabilities

## Problem
ContextEngine used fixed `model_context_tokens` from BudgetConfig profiles. When a larger-context model (e.g., GLM-4.9 with 256K) was deployed, the system still compressed at the small profile's 128K budget, wasting available context window.

## Solution
Pipe provider auto-detected `max_context_tokens` into ContextEngine as an override:

1. **Detection**: `OpenAICompatibleProvider.capabilities()` returns detected context size
2. **Override**: `ContextEngine` accepts `override_max_context_tokens`
3. **Fallback**: If detection fails or returns 0, use BudgetConfig default
4. **Safety**: `AgentLoop.__init__` wraps capability call in try/except for backward compatibility with test providers

## Changes
- `metis/context/engine.py`:
  - Added `override_max_context_tokens` parameter to `ContextEngine.__init__`
  - `max_chars` property uses override when available

- `metis/runtime/loop.py`:
  - `AgentLoop.__init__` probes provider capabilities and passes detected tokens to ContextEngine

## Tests
- `tests/unit/test_context_engine_override.py`:
  - `test_override_max_context_tokens_increases_budget`
  - `test_no_override_uses_budget_default`
  - `test_zero_override_ignored`
  - `test_override_with_threshold`

## Result
942 passed, 10 skipped
