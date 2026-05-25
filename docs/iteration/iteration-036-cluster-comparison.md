# Iteration 036 - Cluster-Aware Eval Comparison

Date: 2026-05-25

## Objective

Make eval run comparison aware of failure families, not only task-level success and scalar metrics.

The purpose is to catch harness regressions that small models can hide behind unchanged aggregate success rates. A run can keep the same task pass/fail status while introducing a new critical failure pattern, such as schema repair collapse, retry-budget exhaustion, missing evidence, or unverified finalization. Those patterns must be visible in the comparison output and must block regression checks when critical.

## Implemented

1. `compare_eval_runs()` now reads cluster artifacts from both baseline and current run directories:
   - `failures/clusters.json`
   - `failures/remediation-backlog.json`

2. Comparison output now includes `cluster_diff`:
   - `new_clusters`
   - `resolved_clusters`
   - `shared_clusters`
   - `new_critical_clusters`
   - `resolved_critical_clusters`
   - `shared_critical_clusters`

3. Regression detection now fails when a new critical cluster appears.

4. Noncritical new clusters are preserved in output but do not alone mark `has_regression=True`.

5. Markdown comparison output now includes a `Cluster Changes` section.

## Design Rationale

Task pass/fail is not enough for a reusable harness. For small 9B or flash-class models, recurring failures often appear first as structural patterns:

- repeated malformed tool arguments
- repeated retry-budget exhaustion
- command execution shapes that keep failing
- evidence references that cannot be resolved
- final answers that claim completion without verifiable evidence
- trajectory/oracle drift where the model uses the wrong tool order

If these are only tracked as per-task failures, a comparison can miss important regressions. Cluster comparison raises the abstraction from individual failed tasks to failure families. This is more useful for harness development because it shows which infrastructure layer degraded.

Critical clusters are treated differently from noncritical clusters. A noncritical trajectory cluster may be an eval prompt issue or a lower-severity workflow issue. A critical cluster represents a direct threat to reliability, trust, or recoverability. For that reason, newly introduced critical clusters block comparison even when success rate stays flat.

## Compatibility

Older eval run directories remain compatible. If cluster files are missing, comparison treats them as empty cluster summaries.

This is intentional because early Metis run artifacts did not include cluster/backlog outputs. Historical baselines can still be compared without migration.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
5 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add explicit severity-change comparison:
   - cluster changed from high to critical
   - cluster changed from critical to high/medium

2. Add count trend comparison:
   - critical cluster count increased
   - total cluster count increased
   - same cluster affected more tasks

3. Add task metadata into failure artifacts:
   - required tools
   - forbidden tools
   - evidence requirements
   - quality gate thresholds

4. Add compact tool-result excerpts to failure artifacts so cluster triage can identify the exact failing output shape without opening the full run trace.
