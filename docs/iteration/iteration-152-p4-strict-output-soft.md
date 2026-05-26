---
iteration: 152
date: 2026-05-26
phase: P4 Engineering Quality
status: completed
---

# Iteration 152: strict_output_soft for 8B Models

## Problem
GLM-4.7-Flash (8B) with `small` profile returned status="blocked" because `strict_output=True`
required JSON format but the model outputs markdown. The repair prompt chain also failed
because 8B models can't reliably produce strict JSON.

## Solution: strict_output_soft mode

### Changes

#### metis/runtime/strict_output.py
- Added `STRICT_OUTPUT_INSTRUCTIONS_SOFT` - friendlier prompt for 8B models
- Added `parse_soft()` - tries JSON parse, then markdown code block extraction, then auto-wraps
  plain text into valid StrictOutput with status="done"
- Added `parse_from_markdown()` - extracts JSON from ```json blocks and bare JSON objects

#### metis/runtime/profiles.py
- Added `strict_output_soft: bool = False` to ModelProfile
- Set `strict_output_soft=True` for `small` profile

#### metis/runtime/loop.py
- Branch: soft mode uses `parse_soft()` without repair prompt (saves API call)
- Hard mode (non-soft) keeps existing repair + strict parse flow
- Fixed indentation: `parsed_final` assignment now correctly inside `else` block

#### metis/prompts/assembler.py
- Added `SMALL_MODEL_IDENTITY` with clearer step-by-step instructions
- Added `strict_output_soft` to PromptParts
- Soft mode uses `SMALL_MODEL_IDENTITY` instead of `BASE_IDENTITY`
- Soft mode uses `STRICT_OUTPUT_INSTRUCTIONS_SOFT` instead of strict instructions

#### tests/
- Updated `test_strict_output_contract.py` - 11 tests (was 3), covers soft mode
- Updated `test_strict_output_block.py` - uses explicit hard profile instead of "small"
- Added `test_glm_small_profile.py` - E2E with real GLM-4.7-Flash API calls

## Test Results
- 488 passed, 0 failed, 3 skipped
- GLM-4.7-Flash + small profile: read_file PASS, write_file PASS
- Previously blocked tasks now complete in 1-3 turns
