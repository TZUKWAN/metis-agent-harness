# Iteration 096: Combined Eval Provenance Hash

Date: 2026-05-25

## Objective

Iteration 095 made release gating require suite schema evidence and task contract evidence. The next gap was fast artifact identity: reviewers and automation still had to inspect multiple fields to understand whether two eval runs were comparable.

This iteration adds a combined provenance payload and hash to eval run artifacts.

## Completed Changes

1. Added `metis.evals.provenance`:
   - `stable_json_hash()`
   - `tool_inventory_hash()`
   - `eval_provenance_payload()`
   - `eval_provenance_hash()`

2. Generic eval metadata now includes:
   - `tool_inventory_hash`

3. Real small-model metadata now includes:
   - `tool_inventory_hash`

4. Generic eval `manifest.json` and `latest.json` now include:
   - `provenance`
   - `provenance_hash`

5. Real small-model `manifest.json` and `latest.json` now include:
   - `provenance`
   - `provenance_hash`

6. The provenance payload includes:
   - `suite`
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_sha256`
   - `task_contract_hash`
   - `model`
   - `base_url`
   - `profile`
   - `tool_inventory_hash`

## Design Notes

The tool inventory hash ignores workspace path and hashes only tool contract fields:

- name
- description
- category
- side effect
- permission requirement
- retry policy
- verification policy
- metadata
- parameters

This avoids making provenance unstable across machines while still detecting changes to the tool surface the model can call.

## Why This Matters

For high-quality 9B/flash eval loops, pass/fail is not enough. A run needs a compact identity that answers:

- Was this the same suite?
- Was this the same schema snapshot?
- Was this the same task contract?
- Was this the same model/profile endpoint?
- Was this the same tool contract surface?

`provenance_hash` is the top-level answer for that artifact identity.

## Verification

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py -q`
  - `49 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_eval_gate.py tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py -q`
  - `136 passed`
- `python -m pytest -q`
  - `333 passed, 4 skipped`

## Remaining Gaps

1. `eval gate` should require `provenance_hash` and a complete provenance payload.
2. `eval compare` should report `provenance_hash` drift directly.
3. `eval diagnose` should create provenance-specific review tasks when only provenance drift occurs.
4. Code-defined suites should write a pre-run provenance contract artifact before provider calls.
