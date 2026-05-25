# Iteration 097: Gate Requires Provenance Evidence

Date: 2026-05-25

## Objective

Iteration 096 introduced `provenance` and `provenance_hash` into eval run artifacts. This iteration makes release gating enforce that evidence.

## Completed Changes

1. `evaluate_eval_run_gate()` now requires provenance evidence by default:
   - non-empty `provenance`
   - `provenance_hash`
   - hash must match the provenance payload

2. The provenance payload must include:
   - `suite`
   - `suite_schema_sha256`
   - `task_contract_hash`
   - `model`
   - `base_url`
   - `profile`
   - `tool_inventory_hash`

3. Gate failures now include explicit provenance errors:
   - `provenance missing from manifest`
   - `provenance_hash missing from manifest`
   - `provenance_hash does not match provenance payload`
   - `provenance.<field> missing from manifest`

4. Gate result now records:
   - `require_provenance_evidence`
   - `run.provenance`
   - `run.provenance_hash`

5. Gate Markdown now renders:
   - `Provenance hash`

6. CLI `metis eval gate --run ...` explicitly passes:
   - `require_provenance_evidence=True`

## Why This Matters

Schema evidence and task contract evidence are necessary, but incomplete. A release decision also needs to know whether the model endpoint, profile, and tool surface are the same. `provenance_hash` provides a compact integrity anchor for that broader artifact identity.

For a 9B/flash model harness, this prevents a subtle failure mode: a run may pass because it used a different tool inventory, profile, endpoint, or task/schema contract, while the report still looks like a normal pass.

## Verification

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - included in `92 passed` combined related run
- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py -q`
  - `141 passed`
- `python -m pytest -q`
  - `338 passed, 4 skipped`
- `python -m compileall -q metis`
  - passed

## Remaining Gaps

1. `eval compare` should report provenance hash drift directly.
2. `eval diagnose` should generate provenance review tasks.
3. Code-defined suites should write pre-run provenance artifacts before model calls.
