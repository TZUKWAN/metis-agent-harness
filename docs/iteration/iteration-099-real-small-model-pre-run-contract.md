# Iteration 099: Real Small-Model Pre-run Contract

Date: 2026-05-25

## Objective

Previous iterations made post-run artifacts provenance-rich. The remaining gap was that the real small-model path still spent provider tokens before writing a contract artifact that proves what it intended to run.

This iteration writes a pre-run contract before the real provider call.

## Completed Changes

1. Added `real_small_model_pre_run_contract()`:
   - builds the code-defined task list;
   - records metadata;
   - records full task specs;
   - records per-task hash summary;
   - records suite-level task contract hash;
   - records provenance payload;
   - records provenance hash.

2. Added `pre_run_contract_to_markdown()`.

3. Added `write_real_small_model_pre_run_contract()`:
   - writes `pre-run-contract.json`;
   - writes `pre-run-contract.md`;
   - writes under the resolved run directory.

4. Updated `run_and_write_real_small_model_eval_suite()`:
   - resolves `run_name` once;
   - writes the pre-run contract before calling the provider;
   - writes final reports to the same resolved run directory.

5. Updated CLI `metis eval real-small-model`:
   - resolves `run_name` once;
   - writes the pre-run contract before `run_real_small_model_eval_suite()`;
   - prints the pre-run contract directory;
   - writes final reports to the same run directory.

## Artifact Shape

The JSON contract includes:

- `artifact_type`
- `suite`
- `suite_definition_type`
- `schema_version`
- `run_name`
- `requested_run_name`
- `generated_at`
- `workspace`
- `metadata`
- `task_count`
- `task_contract_hash`
- `task_spec_hash_summary`
- `task_specs`
- `provenance`
- `provenance_hash`

## Why This Matters

For real 9B/flash endpoints, token spend and external provider calls should be tied to a pre-run contract. If the run crashes, times out, or is interrupted, the harness should still preserve:

- what task set was about to run;
- what schema snapshot applied;
- what tool surface was exposed;
- what model endpoint/profile was configured;
- what provenance fingerprint describes the run.

This makes failed or interrupted real-model evals auditable instead of invisible.

## Verification

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`
  - `51 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_eval_gate.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\e2e\test_local_9b_eval.py -q`
  - `148 passed, 3 skipped`
- `python -m pytest -q`
  - `340 passed, 4 skipped`

## Remaining Gaps

1. Generic `run-suite` should also write a pre-run contract before provider calls.
2. Pre-run contract should be linked from `manifest.json` after the run completes.
3. Gate should verify that the post-run manifest provenance matches the pre-run contract provenance.
4. Compare should report pre-run/post-run provenance mismatch.
