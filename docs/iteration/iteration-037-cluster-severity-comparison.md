# Iteration 037 - Cluster Severity Comparison

Date: 2026-05-25

## Objective

Extend eval comparison beyond new/resolved cluster keys by detecting severity movement inside shared clusters.

This matters because a failure family can already exist in a baseline and still become materially worse. If a shared cluster changes from `high` or `medium` to `critical`, the harness must treat that as a regression even when no new cluster key appears.

## Implemented

1. Cluster summaries now include severity by cluster key, read from:
   - `failures/remediation-backlog.json`

2. `cluster_diff` now includes:
   - `severity_changes`
   - `critical_severity_upgrades`
   - `severity_downgrades`

3. `has_regression` now becomes true when:
   - a new critical cluster appears; or
   - a shared cluster becomes critical.

4. Markdown comparison output now includes:
   - critical severity upgrades
   - severity downgrades

## Design Rationale

New cluster keys catch newly introduced failure families. Severity comparison catches worsening known failure families.

For Metis, this distinction is important because the harness is meant to support repeated small-model hardening. A known low-frequency trajectory issue may be acceptable during development. If that same family becomes critical because it now affects evidence, finalization, schema repair, or retry exhaustion, the run has degraded even if the cluster key did not change.

Severity downgrades are not treated as regressions. They are recorded so the report can show recovery and make baseline comparisons useful for long-running improvement work.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
7 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Compare cluster counts:
   - current count greater than baseline count
   - current affected task count greater than baseline affected task count
   - current critical cluster count greater than baseline critical cluster count

2. Enrich failure artifacts:
   - task spec metadata
   - required and forbidden tools
   - evidence policy
   - quality gate thresholds
   - compact tool output excerpts

3. Add compare gate profile:
   - strict mode blocks any cluster count increase
   - release mode blocks critical increases only
   - exploratory mode records all diffs without blocking
