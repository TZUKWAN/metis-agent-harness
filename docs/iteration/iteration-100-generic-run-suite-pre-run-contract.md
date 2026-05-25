# Iteration 100: Generic Run-suite Pre-run Contract

Date: 2026-05-25

## Objective

Iteration 099 added pre-run contracts for `real-small-model`. This iteration extends the same guarantee to generic loadable eval suites.

The goal is that `metis eval run-suite` writes the exact suite/task/provenance contract before making provider calls.

## External Research Notes

Recent checks reinforced the same direction:

- MLflow dataset/evaluation tracking records dataset identity and digest before/with evaluation runs.
- OpenTelemetry GenAI semantic conventions include GenAI tool definitions and evaluation attributes.
- Agent manifest/provenance materials emphasize declaring capabilities, operational boundaries, and run identity before interaction.

For Metis this means the pre-run contract should include suite identity, schema, task specs, task hashes, tool surface hash, provider/profile metadata, and provenance hash.

## Completed Changes

1. Added `generic_eval_pre_run_contract()`:
   - loads the suite payload;
   - loads executable `EvalTaskSpec` objects;
   - records generic eval metadata;
   - records full task specs;
   - records `task_spec_hash_summary`;
   - records `task_contract_hash`;
   - records `provenance`;
   - records `provenance_hash`.

2. Added `pre_run_contract_to_markdown()` for generic suite contracts.

3. Added `write_generic_eval_pre_run_contract()`:
   - writes `pre-run-contract.json`;
   - writes `pre-run-contract.md`.

4. Updated `run_and_write_generic_eval_suite()`:
   - resolves `run_name` once;
   - writes pre-run contract before provider calls;
   - writes post-run reports to the same resolved directory.

5. Updated CLI `metis eval run-suite`:
   - resolves `run_name` once;
   - writes pre-run contract before `run_generic_eval_suite()`;
   - prints the pre-run contract directory;
   - writes final reports to the same resolved run directory.

6. Exported generic pre-run helpers through `metis.evals`.

## Artifact Shape

`pre-run-contract.json` includes:

- `artifact_type`
- `suite`
- `suite_path`
- `schema_version`
- `run_name`
- `requested_run_name`
- `generated_at`
- `workspace`
- `profile`
- `metadata`
- `task_count`
- `task_contract_hash`
- `task_spec_hash_summary`
- `task_specs`
- `provenance`
- `provenance_hash`

## Verification

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py -q`
  - `53 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_eval_gate.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\e2e\test_local_9b_eval.py -q`
  - `150 passed, 3 skipped`
- `python -m pytest -q`
  - `342 passed, 4 skipped`

## Remaining Gaps

1. Gate should verify post-run manifest provenance matches `pre-run-contract.json`.
2. Compare should report pre-run/post-run mismatch.
3. Trace export should include the pre-run provenance hash as a run-level attribute.
