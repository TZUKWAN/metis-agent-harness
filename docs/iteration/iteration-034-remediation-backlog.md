# Iteration 034 - Remediation Backlog

## Purpose

Failure clusters identify repeated failure families, but the improvement loop still needs a repair queue. Metis should turn each cluster into a concrete action item with severity, owner area, recommended action, and a suggested eval to add.

This iteration adds deterministic remediation backlog generation.

## Outputs

`EvalSuiteResult.write_reports()` now writes:

- `failures/clusters.json`
- `failures/clusters.md`
- `failures/remediation-backlog.json`
- `failures/remediation-backlog.md`

## Backlog Item Fields

Each item contains:

- `id`
- `cluster_key`
- `severity`
- `owner_area`
- `affected_task_ids`
- `recommended_action`
- `suggested_eval`
- `signals`

## Severity Rules

Current deterministic severity:

- `critical`
  - schema failures
  - retry budget failures
  - evidence resolution failures
  - unverified finalization
- `high`
  - trajectory failures
  - repeated failure shapes
  - clusters with count >= 3
- `medium`
  - all other deterministic failure clusters

## Owner Areas

Current owner areas:

- `tool-schema-and-repair`
- `runtime-lineage-and-recovery`
- `evidence-and-finalization`
- `tool-command-execution`
- `eval-oracles-and-prompts`
- `harness-runtime`

## Suggested Eval Rules

Examples:

- schema cluster:
  - add a schema-repair eval that reproduces malformed arguments and requires one corrected retry.
- retry/shape cluster:
  - add a lineage regression eval that repeats the failure shape and asserts retry/pre-dispatch bounds.
- evidence/finalization cluster:
  - add a verified-final eval requiring final evidence refs to match tool-provided ids.
- command failure cluster:
  - add a command-recovery eval requiring interpretation of nonzero exit output and safe correction.
- trajectory cluster:
  - add an oracle eval covering required tools, forbidden tools, required order, and required arguments.

## Tests

Updated:

- `tests/unit/test_failure_clusters.py`
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

1. Add cluster gates:
   - fail on new critical cluster types
   - fail on critical cluster count increase
2. Compare remediation backlog across runs.
3. Include task spec metadata in failure artifacts.
4. Include compact tool result excerpts in failure artifacts.
5. Add one-command export of remediation backlog for issue trackers.
