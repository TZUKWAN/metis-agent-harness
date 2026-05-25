# Iteration 131 - Compare Artifact Path Diagnostic Summary

Date: 2026-05-25

## Problem

Iteration 130 added `artifact_path_diagnostic_summary` to generated targeted eval stubs and materialized suites. That helped dashboards after repair-suite generation, but the compare report itself still lacked the same compact diagnostic surface.

Release tooling often starts at `eval compare`, before targeted stubs are written. If artifact path policy issues are visible only after materialization, CI and reviewers have to take an extra step to understand whether a `quality_gate_failed` regression is partly caused by non-portable artifact metadata.

## Implementation

`compare_eval_runs()` now derives artifact path diagnostics directly from `quality_gate_diff.new_failed_gates`.

Comparison JSON now includes:

```json
"artifact_path_diagnostics": [],
"artifact_path_diagnostic_summary": {
  "total": 0,
  "by_reason": {},
  "by_source": {},
  "by_gate": {},
  "by_task": {}
}
```

The `quality_gate_failed` regression reason link now also carries:

- `artifact_path_diagnostics`
- `artifact_path_diagnostic_summary`

Comparison Markdown now renders:

- artifact path diagnostic summary in the Quality Gate Drift section;
- artifact path diagnostic details in the Quality Gate Drift section;
- compact diagnostic summary in the `quality_gate_failed` reason link line when present.

## Harness Impact

This moves artifact path hygiene observability one stage earlier:

1. Compare reports can show path-contract hygiene before targeted eval generation.
2. Release gates and CI can consume the summary from comparison JSON directly.
3. Quality gate regressions now carry both gate drift and artifact-contract diagnostics in the same link payload.
4. Generated stubs/suites and compare reports now share the same diagnostic vocabulary.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
python -m compileall -q metis
```

Result:

```text
54 passed
compileall passed
```

## Remaining Work

1. Add release-gate policy thresholds for artifact path diagnostics when they indicate generated suite hygiene problems.
2. Add dashboard rendering for compare-level diagnostic summaries.
3. Add trend comparison of artifact diagnostic summaries across baseline/current runs.
4. Add signed artifact bundle attestation.
