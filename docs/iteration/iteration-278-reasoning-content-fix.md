# Iteration 278: Fix Missing reasoning_content for Thinking-Enabled Models

## Problem
GLM API returned `400 thinking is enabled but reasoning_content is missing in assistant tool call message` when:
1. Model had thinking enabled (e.g., glm-4.7-flash)
2. Assistant message contained `tool_calls`
3. But `reasoning_content` was missing

This broke multi-turn sessions with tool calls on thinking-enabled models.

## Solution

1. **Always add reasoning_content on new tool call messages**: In `AgentLoop.run()`, when constructing the assistant_message with tool_calls, if `reasoning_content` is absent, set it to `reasoning or ""`.

2. **Sanitize historical messages before provider calls**: Added `_ensure_reasoning_content()` static method that scans the message list before sending to the provider. For known thinking-enabled model families (glm-4.7, glm-4.9, glm-4.5, claude), it injects an empty `reasoning_content` into any assistant message that has `tool_calls` but lacks `reasoning_content`.

## Changes
- `metis/runtime/loop.py`:
  - Added `_ensure_reasoning_content()` static method
  - Call it on `context_result.messages` before `provider.complete()`
  - Modified assistant_message construction to always include `reasoning_content` when `tool_calls` exist

## Tests
- `tests/unit/test_reasoning_content_fix.py`:
  - `test_assistant_message_gets_reasoning_content_on_tool_call`
  - `test_provider_messages_sanitized_for_thinking_model`
  - `test_ensure_reasoning_content_skips_non_thinking_models`
  - `test_ensure_reasoning_content_adds_for_glm47`
  - `test_ensure_reasoning_content_preserves_existing`

## Result
742 passed, 0 failed
