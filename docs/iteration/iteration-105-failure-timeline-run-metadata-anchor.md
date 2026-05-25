# Iteration 105 - Failure Timeline Run Metadata Anchor

This iteration carries pre-run contract and run provenance anchors into failed task timelines.

## Problem

The eval artifact chain already had strong run-level provenance:

1. pre-run contract files are written before provider calls;
2. manifests/latest pointers record pre-run contract path and SHA256;
3. release gate verifies those anchors;
4. compare verifies those anchors across runs.

The remaining gap was trace review. A failed task timeline showed task events, tool failures, schema repair hints, and finalization errors, but did not show the run-level contract identity. A human or repair generator opening one timeline had to infer which pre-run contract, task contract, suite schema, and provenance hash governed the failure.

## Changes

1. Added `annotate_failure_timelines(output_dir, run_metadata)`.
2. The helper reads `failures/index.json`, updates each failed task timeline JSON with a top-level `run_metadata`, and regenerates timeline Markdown.
3. Real-small-model report writing calls the helper after manifest generation.
4. Generic run-suite report writing calls the helper after manifest generation.
5. Timeline `run_metadata` includes:
   - `suite`
   - `run_name`
   - `requested_run_name`
   - `suite_definition_type`
   - `schema_version`
   - `suite_schema_id`
   - `suite_schema_path`
   - `suite_schema_sha256`
   - `task_contract_hash`
   - `provenance_hash`
   - `pre_run_contract_path`
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
6. Failure timeline Markdown now renders these anchors.
7. `metis trace show` also renders these anchors through the shared telemetry timeline renderer.

## Why This Matters

A high-quality harness for small models must reduce ambiguity. When a 9B model fails, the harness should give the next repair step exact evidence instead of asking the model to infer context from scattered artifacts.

With this change, each failed timeline carries:

1. the task-level failure trajectory;
2. the run-level contract identity;
3. the pre-run artifact digest;
4. the post-run provenance hash.

That makes failed timelines portable, auditable, and useful as direct inputs to repair planning.

## Validation

- `python -m pytest tests\unit\test_eval_suite_run.py tests\unit\test_eval_runner.py tests\unit\test_timeline.py tests\unit\test_cli_eval.py -q`
- Result: `100 passed`

## References Checked

- OpenTelemetry guidance emphasizes resource/span attributes for runtime context.
- Agent trace evaluation guidance emphasizes diagnosing failures from complete execution traces.
- Artifact provenance guidance emphasizes binding traceable artifacts to digests.

## Next Gaps

1. Propagate timeline `run_metadata` into diagnosis entries and repair tasks.
2. Add `run-attestation.json` covering manifest, pre-run contract, task specs, reports, failure artifacts, and timelines.
3. Add OpenTelemetry-compatible JSON export for local timelines.
4. Split compare trust status into baseline/current trust categories.
5. Add suite-scoped latest pointers for generic suites.
