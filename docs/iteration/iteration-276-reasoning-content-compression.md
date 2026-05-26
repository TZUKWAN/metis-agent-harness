# Iteration 276: Account for reasoning_content in Context Compression

## Problem
Assistant messages from thinking-enabled models (e.g., GLM-4.7-flash) may contain `reasoning_content` (chain-of-thought) that was invisible to the context compressor. This caused two issues:

1. **Size underestimation**: `_count_chars` only measured `content`, so messages with long reasoning chains appeared smaller than they actually were, potentially causing context budget overflows.
2. **Unprotected eviction**: `reasoning_content` carried valuable model reasoning but had no priority protection during compression, risking loss of critical problem-solving context.

## Solution

1. **Count `reasoning_content`**: Both `ContextEngine._count_chars` and `SimpleContextCompressor._count_chars` now sum `content` + `reasoning_content` lengths.
2. **Priority scoring**: `_score_message` assigns score 65 to assistant messages with `reasoning_content` (between plain text=50 and tool_calls=70), ensuring reasoning is preserved over generic text but not above actionable tool calls.

## Changes
- `metis/context/engine.py`: `_count_chars` includes `reasoning_content`
- `metis/context/compressor.py`:
  - `_count_chars` includes `reasoning_content`
  - `_score_message` gives reasoning-bearing assistants score 65

## Tests
- `tests/unit/test_reasoning_content_compression.py`:
  - `test_engine_count_chars_includes_reasoning`
  - `test_compressor_count_chars_includes_reasoning`
  - `test_score_assistant_with_reasoning_higher_than_text`
  - `test_score_assistant_with_tools_higher_than_reasoning`
  - `test_compression_triggered_by_reasoning_content`
  - `test_force_fit_preserves_reasoning_content`

## Result
726 passed, 0 failed
