# Iteration 270: Auto-Detect Provider Capabilities

## Problem
Provider capabilities (thinking support, context length, output length) were manually configured via environment variables or hardcoded heuristics. This led to:
- Wrong thinking mode for deployed models
- Suboptimal context compression due to incorrect context length assumptions
- Manual configuration burden when switching models

## Solution
Add automatic model capability detection based on model name patterns:

1. **Capability registry** (`_MODEL_CAPABILITIES`): Known model name prefixes mapped to their capabilities
2. **Pattern matching**: `glm-4.7` → thinking=True, 128K context, 8K output
3. **Env var override**: Environment variables still take precedence for customization
4. **Unknown model fallback**: Safe defaults (no thinking, 0 context tokens)

Supported models:
- GLM-4.9: thinking, 256K context, 16K output
- GLM-4.7/4.5: thinking, 128K context, 8K output
- GLM-4: no thinking, 128K context, 4K output
- GPT-4o/4o-mini: no thinking, 128K context, 16K output
- Claude 3.5 Sonnet: no thinking, 200K context, 8K output

## Changes
- `metis/providers/openai_compat.py`:
  - Added `_MODEL_CAPABILITIES` class-level dict
  - Added `_detect_model_capabilities()` class method
  - Rewrote `capabilities()` to use detection + env var override

## Tests
- `tests/unit/test_provider_capabilities.py`:
  - `test_glm47_flash_detects_thinking`
  - `test_glm45_detects_thinking`
  - `test_glm49_detects_larger_context`
  - `test_glm4_no_thinking`
  - `test_gpt4o_no_thinking`
  - `test_claude_sonnet_context`
  - `test_unknown_model_defaults`
  - `test_env_var_overrides_detection`
  - `test_to_dict_serializes_retryable_codes`

## Result
938 passed, 10 skipped
