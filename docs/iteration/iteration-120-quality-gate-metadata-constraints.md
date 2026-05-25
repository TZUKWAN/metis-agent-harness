# Iteration 120 - Quality Gate Metadata Constraints

This iteration compiles quality gate drift metadata into executable targeted eval constraints.

## Problem

Iteration 119 preserved gate drift context in targeted eval stubs and materialized suites. That was necessary, but still left too much interpretation to the model.

If a failed gate already carries structured metadata such as an artifact path or required evidence source, the harness should convert that metadata into the `EvalTaskSpec` contract directly.

## Changes

1. Targeted eval generation now derives `expected_artifacts` from quality gate metadata.
2. Targeted eval generation now derives `required_evidence_sources` from quality gate metadata.
3. Artifact-path extraction supports:
   - `path`
   - `paths`
   - `artifact_path`
   - `artifact_paths`
   - `expected_artifact`
   - `expected_artifacts`
4. Evidence-source extraction supports:
   - `source_type`
   - `source_types`
   - `evidence_source`
   - `evidence_sources`
   - `required_evidence_source`
   - `required_evidence_sources`
5. Artifact-oriented gates are mapped to artifact constraints:
   - `artifact_exists`
   - `artifact_non_empty`
   - `no_placeholder`
6. Materialized targeted suites preserve these constraints because they live inside `task_spec`.

## Why This Matters

Small models should not have to infer harness contracts from prose when the metadata is already machine-readable.

This change turns gate drift into a stronger regression task:

```text
quality gate metadata path=outputs/report.md
-> targeted eval expected_artifacts=["outputs/report.md"]
-> runner verifies artifact presence directly
```

The model still performs the task, but the harness owns the quality boundary.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `50 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Default gates should emit richer, standardized metadata on failure.
2. `requirements_covered` should expose missing requirements in structured metadata.
3. Release gates should enforce required gate presence.
4. Gate-level dashboard trends should be generated from `quality_gate_names`.
5. Run attestations should be signed.
