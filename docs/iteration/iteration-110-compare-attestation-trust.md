# Iteration 110 - Compare Attestation Trust

This iteration makes `eval compare` understand run artifact attestation trust.

## Problem

Iteration 109 made `eval gate` verify `run-attestation.json`. That protects a single run at release time.

The remaining gap was cross-run comparison. A baseline or current run directory can be copied, partially edited, synced from another machine, or manually repaired. If `eval compare` reads those directories without checking their attestation state, it can mistake artifact corruption for model or harness behavior.

## Changes

1. `compare_eval_runs()` now computes `attestation_diff`.
2. `attestation_diff` includes:
   - `baseline_present`
   - `current_present`
   - `baseline_failures`
   - `current_failures`
   - `comparison_attestation_failures`
3. Compare reuses `verify_run_attestation(run_dir)`.
4. Compatibility policy:
   - if both runs have no attestation, compare remains legacy-compatible;
   - if one run has attestation and the other is missing it, the missing side is untrusted;
   - if either attestation exists but fails digest, size, structure, or required-subject verification, that side is untrusted.
5. Release and strict profiles now add:
   - `attestation_untrusted`
6. Regression reason links include the attestation failure list.
7. Comparison Markdown now has:
   - `## Artifact Attestation`
8. The recommended action for `attestation_untrusted` tells repair flows to fix auditability before interpreting behavior deltas.

## Why This Matters

Metis uses eval runs as long-lived training signals for repair, regression, and harness tuning. Those run directories are artifacts, not just logs.

If a historical run has a stale report, missing task specs, or mismatched manifest, the right response is not to tune the model. The right response is to reject the comparison as unauditable.

The comparison rule is now:

```text
If either attested run cannot verify, release/strict comparison is untrusted.
```

Legacy runs are still readable when both sides predate attestation, but mixed old/new or tampered bundles are surfaced explicitly.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `45 passed`

## Remaining Gaps

1. Add explicit top-level `baseline_untrusted` and `current_untrusted` booleans.
2. Render subject counts and failing subject names in `comparison.md`.
3. Map `attestation_untrusted` to a dedicated artifact repair owner area.
4. Generate attestations for targeted eval stubs, materialized suites, and repair plans.
5. Add signing support for attestation statements.
