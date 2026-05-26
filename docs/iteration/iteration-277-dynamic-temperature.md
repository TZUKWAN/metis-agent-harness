# Iteration 277: Dynamic Temperature Adjustment

## Problem
Model temperature was fixed at 0.2 regardless of turn state. On long-running sessions or after repeated failures, the 8B model could get stuck in repetitive response patterns. A slightly higher temperature encourages more diverse outputs when the model is struggling.

## Solution
Dynamically adjust `temperature` passed to `provider.complete()` based on turn state:

- **Base**: 0.2
- **Turn boost**: +0.05 per turn, capped at +0.35 (max 7 turns worth)
- **Repair boost**: +0.1 if any tool repair failures occurred
- **Loop risk boost**: +0.15 if the last two turn signatures match
- **Clamp**: [0.0, 0.8]

## Changes
- `metis/runtime/loop.py`:
  - Added `_compute_temperature()` static method
  - Calculate temperature before each `model.request` trace event
  - Pass `temperature` parameter to `provider.complete()` calls
  - Record `temperature` in `model.request` trace event attributes

## Tests
- `tests/unit/test_dynamic_temperature.py`:
  - `test_temperature_base_on_first_turn`
  - `test_temperature_increases_with_turn_index`
  - `test_temperature_turn_boost_capped`
  - `test_temperature_increases_with_repair_failures`
  - `test_temperature_increases_with_loop_risk`
  - `test_temperature_combined_boosts`
  - `test_temperature_clamped_maximum`
  - `test_temperature_no_loop_boost_with_single_signature`
  - `test_temperature_no_loop_boost_with_different_signatures`
  - `test_provider_receives_dynamic_temperature`
  - `test_temperature_increases_on_second_turn`

## Result
737 passed, 0 failed
