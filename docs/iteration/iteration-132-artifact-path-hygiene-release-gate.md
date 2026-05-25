# Iteration 132 - Artifact Path Hygiene Release Gate

Date: 2026-05-25

## Problem

Iterations 129-131 made artifact path diagnostics visible and aggregated. Visibility alone is not enough for release-grade harness behavior.

If a release comparison contains:

- absolute artifact paths;
- Windows drive-prefixed artifact paths;
- parent traversal artifact paths;

then the generated eval contract is not portable and may be unsafe. That should block release/strict profiles instead of appearing only as auxiliary metadata.

## Implementation

`compare_eval_runs()` now emits a new regression reason:

```text
artifact_path_hygiene_failed
```

The reason is emitted for release and strict profiles when `artifact_path_diagnostic_summary.total > 0`.

The regression reason link includes:

- `task_ids`
- `artifact_paths`
- `timeline_paths`
- `artifact_path_diagnostics`
- `artifact_path_diagnostic_summary`

Markdown reason links include the compact artifact path diagnostic summary.

Repair task routing now handles this reason:

- owner area: `eval-suite-hygiene`
- recommended action: remove non-portable artifact paths from quality gate metadata, generated suites, or eval fixtures before release
- suggested eval: add a suite hygiene regression that fails on absolute, drive-prefixed, or parent-traversal artifact paths

## Harness Impact

This changes artifact path hygiene from "visible warning" to "release blocker."

For a reusable scenario-agnostic agent harness, this matters because:

1. Repair suites must be portable across machines.
2. A model or tool should not be able to smuggle local filesystem assumptions into eval contracts.
3. CI can block release immediately when artifact metadata violates path policy.
4. Repair planning now assigns this class of issue to the correct owner area instead of mixing it with generic quality gate failures.

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

1. Add configurable severity thresholds for artifact path hygiene diagnostics.
2. Add dashboard rendering for `artifact_path_hygiene_failed`.
3. Add trend comparison of artifact path diagnostics across runs.
4. Add real small-model eval cases that intentionally produce path hygiene failures.
