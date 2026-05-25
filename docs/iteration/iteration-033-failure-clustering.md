# Iteration 033 - Failure Clustering

## Purpose

Metis now exports per-failed-task JSON artifacts. The next step is to turn individual failures into actionable groups. A small-model harness improves fastest when repeated failure families are visible: schema failures, retry-budget failures, evidence failures, command failures, and trajectory failures need different remediation.

This iteration adds deterministic failure clustering.

## New Module

Added:

```text
metis/evals/failures.py
```

Public helpers:

- `cluster_failure_artifacts(failures_dir)`
- `failure_clusters_to_markdown(clusters)`
- `write_failure_clusters(failures_dir)`

## Report Integration

`EvalSuiteResult.write_reports()` now writes:

- `failures/index.json`
- `failures/<safe-task-id>.json`
- `failures/clusters.json`
- `failures/clusters.md`

Clusters are written even when no failures exist. Empty runs produce:

```json
{
  "failure_count": 0,
  "cluster_count": 0,
  "clusters": []
}
```

## Cluster Dimensions

Current deterministic dimensions:

- tool failure type
- failure shape key
- trajectory failure
- schema failure
- retry budget failure
- evidence resolution failure
- unverified finalization
- unknown failure fallback

## Remediation Guidance

Each cluster includes deterministic remediation text. Examples:

- schema failure:
  - tighten tool schema feedback
  - add argument examples
  - preserve schema repair gates
- retry budget failure:
  - improve failure lineage blocking
  - reduce repeated retries
  - add task-specific recovery hints
- command failure:
  - add safer command templates
  - improve command result interpretation
  - add recovery-specific feedback
- evidence failure:
  - improve evidence ref propagation
  - require existing evidence ids in final answers
- trajectory failure:
  - review task oracle gates
  - review required tool order
  - tighten prompt constraints for small-model compliance

## Tests

Added:

- `tests/unit/test_failure_clusters.py`

Updated:

- `tests/unit/test_eval_runner.py`

Executed:

```bash
python -m pytest -q tests\unit\test_failure_clusters.py tests\unit\test_eval_runner.py
python -m compileall -q metis
```

Result:

```text
30 passed
```

## Remaining Work

Next highest-value improvements:

1. Add task spec metadata to failure artifacts so clusters can reference expected tool behavior.
2. Add repair recommendation backlog generation:
   - one backlog item per cluster
   - severity
   - owner area
   - suggested test to add
3. Add cluster trend comparison across runs.
4. Add failure cluster gates:
   - no new cluster types
   - no increase in critical cluster counts
5. Add trace snippets/tool-result excerpts to failure artifacts.
