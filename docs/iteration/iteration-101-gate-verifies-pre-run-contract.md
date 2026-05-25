# Iteration 101: Gate Verifies Pre-run Contract

Date: 2026-05-25

## Objective

Iterations 099 and 100 added `pre-run-contract.json` for real-small-model and generic run-suite paths. This iteration makes release gate verify that the post-run manifest still matches the pre-run contract.

## External Research Notes

This follows the same identity/integrity pattern used in adjacent systems:

- MLflow records dataset hash/digest metadata for evaluation inputs.
- GitHub artifact attestations establish provenance and integrity claims for generated artifacts.
- OpenTelemetry GenAI guidance emphasizes tool definitions and run context as part of observability.
- Agent manifest/provenance practices emphasize declaring capabilities and boundaries before interaction.

For Metis, `pre-run-contract.json` is the pre-provider declaration; `manifest.json` is the post-run declaration. Release gate must reject drift between them.

## Completed Changes

1. `evaluate_eval_run_gate()` now has:
   - `require_pre_run_contract_evidence=True`

2. Gate loads:
   - `<run-dir>/pre-run-contract.json`

3. Gate now fails when:
   - `pre-run-contract.json` is missing;
   - pre-run provenance is missing;
   - pre-run `provenance_hash` does not match pre-run provenance payload;
   - pre-run `provenance_hash` differs from manifest `provenance_hash`;
   - pre-run `task_contract_hash` differs from manifest `task_contract_hash`;
   - pre-run `task_spec_hash_summary` differs from manifest `task_spec_hash_summary`.

4. Gate result now records:
   - `require_pre_run_contract_evidence`
   - `run.pre_run_contract_path`
   - `run.pre_run_provenance_hash`

5. Gate Markdown now renders:
   - `Pre-run provenance hash`

6. CLI `metis eval gate --run ...` explicitly passes:
   - `require_pre_run_contract_evidence=True`

## Why This Matters

Without this check, a run could write a correct pre-run contract, then write a different post-run manifest. That would make the artifact look auditable while still allowing silent drift in task contract, task hashes, or provenance.

For 9B/flash model work, this prevents false evaluation confidence when the harness, suite, tools, profile, or model endpoint changes between contract generation and final reporting.

## Verification

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - `55 passed`
- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\e2e\test_local_9b_eval.py -q`
  - `153 passed, 3 skipped`
- `python -m pytest -q`
  - `345 passed, 4 skipped`
- `python -m compileall -q metis`
  - passed

## Remaining Gaps

1. `eval compare` should report pre-run/post-run mismatch.
2. `eval diagnose` should generate provenance review tasks.
3. Trace exports should include pre-run provenance hash as run-level metadata.
