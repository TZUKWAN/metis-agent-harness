# Iteration 035 - Cluster-aware Release Gate

## Purpose

Metis release gates already check success rate and core trajectory metrics. After adding failure clustering and remediation backlog, the gate should also reject runs with unresolved critical failure families. Otherwise a run could pass relaxed task thresholds while still containing repeated schema, retry, evidence, or finalization failure modes.

This iteration makes `metis eval gate` cluster-aware.

## Gate Additions

New default thresholds:

- `max_failure_clusters=0`
- `max_critical_remediations=0`

New CLI options:

```bash
metis eval gate \
  --run docs/evals/runs/<run-name> \
  --max-failure-clusters 0 \
  --max-critical-remediations 0
```

## Data Sources

The gate reads:

- `eval-report.json`
- `manifest.json`
- `failures/clusters.json`
- `failures/remediation-backlog.json`

Older run directories without cluster files are tolerated and treated as having zero cluster findings.

## New Gate Aggregates

The gate payload now includes:

- `failure_clusters`
- `critical_remediations`

It also includes `cluster_summary`:

- cluster count
- cluster keys
- critical remediation count
- critical cluster keys

## Behavior

The gate fails if:

- `failure_clusters > max_failure_clusters`
- `critical_remediations > max_critical_remediations`

This keeps the default release gate strict while still allowing controlled experimentation through explicit CLI thresholds.

## Tests

Updated:

- `tests/unit/test_eval_gate.py`
- `tests/unit/test_cli_eval.py`

Executed:

```bash
python -m pytest -q tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py
python -m compileall -q metis
```

Result:

```text
16 passed
```

## Remaining Work

Next highest-value improvements:

1. Compare clusters across baseline/current runs:
   - new critical clusters
   - resolved clusters
   - severity changes
2. Add gate mode that fails only on new critical clusters relative to baseline.
3. Add task spec metadata into failure artifacts.
4. Add compact tool result excerpts into failure artifacts.
5. Add model/provider/runtime snapshot into run manifest.
