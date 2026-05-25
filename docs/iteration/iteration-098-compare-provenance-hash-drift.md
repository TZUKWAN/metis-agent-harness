# Iteration 098: Compare Provenance Hash Drift

Date: 2026-05-25

## Objective

Iteration 097 made release gate require provenance evidence. This iteration makes `eval compare` consume that evidence directly.

## Completed Changes

1. `compare_eval_runs()` now computes `provenance_diff`.
2. `provenance_diff` includes:
   - `baseline_provenance_hash`
   - `current_provenance_hash`
   - `provenance_hash_changed`
   - `field_changes`

3. Comparison Markdown now includes:
   - `## Provenance Drift`
   - `Provenance hash changed`
   - `Provenance field changes`

4. Release and strict profiles now treat `provenance_hash_changed` as a regression reason.

5. Regression reason links now include:
   - `provenance_hash_changed`
   - provenance `field_changes`

## Why This Matters

When two eval runs have different provenance fingerprints, behavior deltas are not cleanly attributable to the model or harness. The comparison must surface that before interpreting pass/fail movement, metric deltas, clusters, or schema repair health.

This is particularly important for small-model work because harness improvements are usually measured by many repeated runs. If tool definitions, profile, endpoint, suite schema, or task contract changed, the run is a different experiment.

## Verification

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`
  - `92 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py -q`
  - `141 passed`
- `python -m pytest -q`
  - `338 passed, 4 skipped`

## Remaining Gaps

1. `eval diagnose` should create provenance-specific review tasks.
2. Pre-run provenance contract artifacts should be generated for real-small-model.
3. Trace exports should include provenance hash on run-level events or OTel resource attributes.
