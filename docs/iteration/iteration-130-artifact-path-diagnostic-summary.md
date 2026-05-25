# Iteration 130 - Artifact Path Diagnostic Summary

Date: 2026-05-25

## Problem

Iteration 129 made filtered artifact paths auditable at the individual stub/task level. That was useful for repair review, but dashboards and release reports still needed a compact summary.

Without summary counts, a dashboard has to scan every task-level diagnostic just to answer:

- how many paths were filtered;
- which policy reason dominated;
- which metadata source produced bad paths;
- which gate or task is responsible.

For a production harness, diagnostic detail and aggregated metrics should both exist.

## Implementation

Generated targeted eval stubs now include:

```json
"artifact_path_diagnostic_summary": {
  "total": 0,
  "by_reason": {},
  "by_source": {},
  "by_gate": {},
  "by_task": {}
}
```

Materialized targeted suites include the same top-level summary.

The summary is generated from wrapper-level `artifact_path_diagnostics`, not from `eval_task_spec`, because filtered paths are audit metadata rather than executable model contracts.

Markdown reports now render:

- stub-level summary in `targeted-eval-stubs.md`;
- suite-level summary in `targeted-eval-suite.md`;
- task-level diagnostic details below each task.

## Harness Impact

This gives the harness a compact observability surface:

1. Dashboard code can read one summary object instead of scanning all tasks.
2. Release reports can show whether artifact path hygiene is improving or degrading.
3. A spike in `windows_drive_prefix` or `parent_traversal` immediately points to a suite-generation or metadata source problem.
4. Per-path details remain available for audit and repair.

This is aligned with trace-based agent evaluation practice: failures need both detailed traceability and aggregated signals.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
python -m compileall -q metis
```

Result:

```text
53 passed
compileall passed
```

## Remaining Work

1. Surface `artifact_path_diagnostic_summary` in compare reports when generated stubs are written from comparison output.
2. Add dashboard-specific rendering for reason/source/gate counts.
3. Add real small-model eval cases that intentionally exercise artifact diagnostic summaries.
4. Add signed attestation for artifact bundles.
