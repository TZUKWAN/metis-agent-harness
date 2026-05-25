# Iteration 038 - Cluster Count Trends

Date: 2026-05-25

## Objective

Detect whether an existing failure family expanded between baseline and current eval runs.

New cluster keys and severity changes are not enough. A cluster can keep the same key and same severity while affecting more failures or more tasks. For a production harness, that trend must be visible. For critical clusters, it must block regression checks.

## Implemented

1. Cluster summaries now include:
   - cluster occurrence count
   - affected task count

2. `cluster_diff` now includes:
   - `cluster_count_changes`
   - `cluster_count_increases`
   - `cluster_count_decreases`
   - `affected_task_count_changes`
   - `affected_task_count_increases`
   - `affected_task_count_decreases`
   - `critical_cluster_count_increases`
   - `critical_cluster_affected_task_increases`

3. `has_regression` now becomes true when:
   - a current critical cluster has a higher occurrence count than baseline; or
   - a current critical cluster affects more tasks than baseline.

4. Markdown comparison output now reports:
   - cluster count increases
   - critical cluster count increases
   - critical affected task increases

## Design Rationale

For small-model harness work, a critical failure family getting larger is a real regression even if the success rate is unchanged. It means the model/harness interaction is becoming less recoverable in a known risk area.

The current release behavior is intentionally asymmetric:

- critical cluster expansion blocks the run;
- noncritical cluster expansion is reported but not blocked;
- decreases are recorded as recovery signals.

This keeps strictness focused on reliability, evidence, finalization, and recoverability failures without making every exploratory cluster movement a hard failure.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
9 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add compare profiles:
   - `strict`
   - `release`
   - `exploratory`

2. Add failure artifact enrichment:
   - task spec metadata
   - prompt/instruction hash
   - required/forbidden tools
   - evidence policy
   - compact tool-result excerpts

3. Add trend summary files:
   - `comparison.json`
   - `comparison.md`
   - future `comparison.html`
