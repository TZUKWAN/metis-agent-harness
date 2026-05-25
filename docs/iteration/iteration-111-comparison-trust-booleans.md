# Iteration 111 - Comparison Trust Booleans

This iteration adds direct trust flags to eval comparison output.

## Problem

Iteration 110 introduced `attestation_diff` and the `attestation_untrusted` regression reason. That made release/strict comparison block untrusted run bundles.

The remaining usability issue was machine consumption. CI jobs, dashboards, and repair agents should not need to parse attestation failure strings to know which side is untrusted.

## Changes

1. `compare_eval_runs()` now returns:
   - `baseline_untrusted`
   - `current_untrusted`
2. These booleans are derived from:
   - `attestation_diff.baseline_failures`
   - `attestation_diff.current_failures`
3. Comparison Markdown now renders:
   - `Baseline untrusted`
   - `Current untrusted`
4. Tests cover:
   - current report tampering sets `current_untrusted=True`;
   - one-sided missing current attestation sets `current_untrusted=True`;
   - a verified baseline remains `baseline_untrusted=False`.

## Why This Matters

Metis comparison output is not only for humans. It is an input to automated repair, CI, dashboards, and future agent loops.

The new fields give downstream systems a simple branch:

```text
baseline_untrusted -> repair or regenerate baseline artifact bundle
current_untrusted -> repair or regenerate current artifact bundle
both trusted -> interpret behavior and quality deltas
```

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `45 passed`

## Remaining Gaps

1. Propagate trust booleans into diagnosis entries and repair tasks.
2. Add subject counts and failing subject names to Markdown reports.
3. Add signed attestations.
4. Generate attestations for targeted eval and repair artifacts.
