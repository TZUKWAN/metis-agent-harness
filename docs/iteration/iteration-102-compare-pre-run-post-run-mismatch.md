# Iteration 102 - Compare Pre-Run/Post-Run Mismatch

This iteration makes `eval compare` audit each run's internal contract consistency before trusting cross-run behavior deltas.

## Problem

Iterations 099 and 100 added `pre-run-contract.json` before real provider calls. Iteration 101 made `eval gate` reject a run when that pre-run contract differs from the post-run `manifest.json`.

The remaining gap was comparison. `eval compare` could still compare two final manifests without noticing that one run had a pre-run contract declaring one provenance or task contract and a post-run manifest declaring another. That makes the comparison unauditable: success rate, failure clusters, and repair tasks may be attached to the wrong declared run contract.

## Changes

1. `load_eval_run()` now loads `<run-dir>/pre-run-contract.json` when it exists.
2. `_provenance_diff()` now includes:
   - `baseline_pre_run_post_run_mismatches`
   - `current_pre_run_post_run_mismatches`
   - `pre_run_post_run_mismatches`
3. The mismatch detector validates:
   - pre-run `provenance_hash` against the pre-run provenance payload;
   - pre-run `provenance_hash` against the manifest `provenance_hash`;
   - pre-run `task_contract_hash` against the manifest `task_contract_hash`;
   - pre-run `task_spec_hash_summary` against the manifest `task_spec_hash_summary`.
4. Release and strict compare profiles now treat `pre_run_post_run_mismatch` as a regression reason.
5. Regression reason links include the exact mismatch payloads.
6. Comparison Markdown renders `Pre-run/post-run mismatches` in `## Provenance Drift`.
7. Legacy compatibility is preserved: missing `pre-run-contract.json` does not fail compare by itself; present-but-inconsistent contracts do fail release/strict comparison.

## Why This Matters

Metis is intended to make smaller 9B/flash models produce reliable agent work through harness discipline. That requires every eval artifact to be trustworthy. A run must be auditable at three levels:

1. what it declared before spending provider tokens;
2. what it wrote after execution;
3. how it compares with another run.

This iteration closes the third level for pre-run contract drift.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `41 passed`

## Next Gaps

1. Add pre-run provenance hash and contract path to trace exports.
2. Add explicit baseline-current trust classification in compare output.
3. Normalize provenance mismatch diagnosis codes between gate and compare.
4. Write pre-run contract path/hash into run manifest artifacts.
5. Surface pre-run/post-run mismatch as a first-class dashboard status.
