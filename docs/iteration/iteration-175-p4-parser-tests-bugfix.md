---
iteration: 175
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 175: Add provider parser tests + fix null arguments bug

## Changes
- Added 21 parser tests: HermesXML, OpenAINative, JsonBlock, _try_repair_json, ToolCallParser ABC
- **Bug fix**: OpenAINativeParser crashed on null arguments - `dict(None)` raised TypeError
  - Fixed: `dict(arguments_raw or {})` handles None gracefully
- Hermes tests use dynamic delimiter extraction from TOOL_CALL_RE pattern

## Test Results
- 589 passed, 0 failed, 8 skipped
