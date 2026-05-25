# Iteration 092: Real Small-Model Schema Evidence

Date: 2026-05-25

## Objective

Iteration 091 made independent release gating require suite schema evidence in `manifest.json`. That exposed a real gap in the built-in real small-model eval path:

```bash
metis eval real-small-model --gate
```

This path writes a run directory and then immediately runs the same release gate. Its suite is code-defined rather than loaded from a JSON suite file, so it did not previously write `suite_schema_id` or `suite_schema_sha256` into the run manifest.

The objective for this iteration was to make the real-small-model path provenance-safe without pretending it is a file-loaded generic suite.

## Completed Changes

1. `real_small_model_eval_metadata()` now records:
   - `suite_definition_type: code-defined-builtin`
   - `schema_version: code-defined`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`

2. `real_small_model_eval_manifest()` now writes those fields at the top level:
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`

3. `write_real_small_model_eval_latest_pointer()` now writes:
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_sha256`

4. Unit coverage now proves:
   - real-small-model metadata records the current suite schema snapshot id and SHA256;
   - real-small-model reports persist schema evidence into manifest and latest pointer;
   - manually constructed `EvalSuiteResult` objects still explicitly declare the code-defined suite type even when metadata is incomplete.

## Design Decision

The real-small-model suite is not a JSON suite loaded through `metis eval run-suite --suite`. It is a built-in code-defined suite made from `EvalTaskSpec` objects. Treating it as `"schema_version": "1"` would blur an important distinction: there is no source JSON suite file with a top-level `schema_version` field.

The chosen representation is:

```json
{
  "suite_definition_type": "code-defined-builtin",
  "schema_version": "code-defined",
  "suite_schema_id": "https://metis.local/schemas/evals/suite-schema-v1.json",
  "suite_schema_sha256": "..."
}
```

This says two things at once:

1. The suite definition is code-owned, not file-owned.
2. The task contract and artifact shape are still tied to the current machine-readable suite schema snapshot.

That is the least misleading representation for release provenance.

## Why This Matters

The harness needs a trustworthy evaluation spine for many future agents. The real-small-model suite is especially important because it is the path most likely to run against actual 9B/flash endpoints.

Without this change, the stricter release gate from Iteration 091 could reject real-small-model runs after spending model tokens, or worse, users might relax the gate for the most important real eval path. The correct fix is to make the artifact complete.

## Verification

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_eval_gate.py -q`
  - `58 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q`
  - `111 passed`
- `python -m pytest -q`
  - `329 passed, 4 skipped`

## Remaining Gaps

1. Gate reports should include validation report path/hash when available.
2. Code-defined suites should eventually expose a generated suite contract manifest with task ids, task spec hashes, and schema snapshot hash.
3. Comparison reports should flag changes in suite definition type or schema hash as provenance changes, even when task metrics are unchanged.
4. Latest pointer should eventually include task spec hash summary so a real-small-model run can prove not only which schema existed, but which code-defined task set ran.
