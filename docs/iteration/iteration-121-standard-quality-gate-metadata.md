# Iteration 121 - Standard Quality Gate Metadata

This iteration makes default quality gates emit structured metadata.

## Problem

Iteration 120 compiled quality gate metadata into targeted eval constraints. That only works well when gates produce useful metadata in the first place.

The default artifact and requirement gates still mostly returned human-readable messages. That made downstream comparison, diagnosis, and repair weaker than necessary.

## Changes

1. `artifact_exists` now reports:
   - `expected_artifacts`
   - `missing_artifacts`
   - `artifact_count`
2. `artifact_non_empty` now reports:
   - `expected_artifacts`
   - `empty_artifacts`
   - `artifact_count`
3. `no_placeholder` now reports:
   - `expected_artifacts`
   - `placeholder_artifacts`
   - `placeholder_message`
   - `artifact_count`
4. `requirements_covered` now reports:
   - `requirements`
   - `missing_requirements`
   - `evidence_count`
   - `artifact_count`
5. Success paths also carry basic metadata so dashboards can show what was checked, not only what failed.

## Why This Matters

Gate output is harness evidence.

For a 9B model, a repair task should not depend on parsing text like `Missing artifacts: outputs/report.md`. It should receive a structured field that the harness can compile into `expected_artifacts`.

This strengthens the evidence path:

```text
quality gate failure
-> structured metadata
-> comparison quality_gate_diff
-> repair task quality_gate_changes
-> targeted eval expected_artifacts / required_evidence_sources
```

## Validation

- `python -m pytest tests\unit\test_quality_gates.py -q`
- Result: `5 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Compile `missing_requirements` into targeted eval prompt constraints.
2. Standardize `no_fake_completion` claim/evidence metadata.
3. Add required quality gate presence checks to release gates.
4. Add gate-level trend views.
5. Sign run attestations.
