---
iteration: 171
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 171: Optimize BudgetConfig for 8B models (GLM-4.7-Flash)

## Changes
- Fixed `model_context_tokens` for small profile: 32768 -> 128000 (GLM-4.7-Flash has 128K context)
- Tightened per-tool chars: 6000 -> 4000 (prevent context overflow)
- Tightened per-turn chars: 24000 -> 20000
- Reduced preview chars: 1500 -> 1200
- Lowered context_threshold: 0.55 -> 0.50 (trigger compression earlier for safety)
- Added 6 budget config tests

## Test Results
- 529 passed, 0 failed, 8 skipped
