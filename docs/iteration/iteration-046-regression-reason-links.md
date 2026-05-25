# Iteration 046 - Regression Reason Links

Date: 2026-05-25

## Objective

Turn comparison regression reasons into actionable evidence links.

Before this iteration, `regression_reasons` told the caller what kind of regression was detected, but not where to look next. That forced manual searching through eval reports, cluster files, and failure artifacts.

## Implemented

1. `compare_eval_runs()` now emits `regression_reason_links`.

2. Task-level reasons now link to:
   - task ids
   - current failure artifact paths

3. Metric reasons now link to:
   - task ids
   - metric delta records
   - current failure artifact paths when present

4. Cluster reasons now link to:
   - cluster keys
   - affected task ids from current cluster artifacts
   - current failure artifact paths

5. Task spec drift reasons now link to:
   - task ids
   - task spec hash change records
   - missing baseline/current spec lists

6. Environment drift reasons now link to:
   - changed fields
   - baseline/current values

7. Markdown comparison output now includes:
   - `## Regression Reason Links`

## Design Rationale

An eval harness should shorten diagnosis time.

A regression report that only says `new_critical_clusters` still leaves the user to search for the cluster, then the task, then the failure artifact. Reason links make the comparison report navigable and machine-actionable.

This is also the foundation for automatic repair planning. Once a reason links to a task, artifact, cluster, and metric delta, Metis can generate a deterministic repair checklist without guessing.

## External Calibration

Recent trace-driven debugging and agent observability guidance emphasizes linking failures to representative traces, artifacts, and recurring failure patterns. Sources reviewed this iteration included:

- Trace-driven debugging from production incident to regression test
- Future AGI Error Feed failure clustering
- Holistic Evaluation and Failure Diagnosis of AI Agents

The Metis implementation keeps this local and deterministic by linking comparison reasons to files already produced inside the run directory.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
18 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Generate `failure-diagnosis.md` from reason links.

2. Add machine-readable `diagnosis.json`:
   - reason
   - task ids
   - artifacts
   - cluster keys
   - recommended action

3. Add CLI command:
   - `metis eval diagnose --comparison <comparison-dir>`

4. Link diagnosis entries to remediation backlog items.
