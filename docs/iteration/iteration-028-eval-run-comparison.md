# Iteration 028 - Eval Run Comparison

## Purpose

Timestamped eval runs are useful only if Metis can compare them and identify regressions. A 9B-class agent harness must make quality drift visible: a model or prompt change may keep the same headline success rate while introducing schema violations, retry-budget failures, or trajectory failures.

This iteration adds deterministic run comparison.

## New Module

Added:

```text
metis/evals/compare.py
```

Public helpers:

- `load_eval_run(run_dir)`
- `compare_eval_runs(baseline_dir=..., current_dir=...)`
- `eval_run_comparison_to_markdown(comparison)`
- `write_eval_run_comparison(comparison, output_dir)`

## CLI

New command:

```bash
metis eval compare --baseline docs/evals/runs/<baseline> --current docs/evals/runs/<current>
```

Optional:

```bash
metis eval compare \
  --baseline docs/evals/runs/<baseline> \
  --current docs/evals/runs/<current> \
  --output-dir docs/evals/comparisons/<name> \
  --json
```

Exit codes:

- `0`: no regression detected.
- `1`: regression detected.

## Regression Definition

The comparison marks a regression when any of the following is true:

1. Current success rate is lower than baseline.
2. A task that passed in baseline fails in current.
3. A tracked negative metric increases.

Tracked negative metrics:

- `parser_failures`
- `tool_failures`
- `quality_failures`
- `false_completion`
- `final_unverified`
- `duplicate_tool_calls`
- `invalid_tool_calls`
- `policy_blocks`
- `evidence_resolution_failures`
- `schema_violations`
- `schema_repair_failures`
- `tool_repair_failures`
- `retry_budget_exhaustions`
- `pre_dispatch_blocks`
- `trajectory_failures`

The comparison also reports:

- recovered tasks
- still failed tasks
- new tasks
- removed tasks
- per-task metric deltas

## Tests

Added:

- `tests/unit/test_eval_compare.py`

Updated:

- `tests/unit/test_cli_eval.py`

Executed:

```bash
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
python -m compileall -q metis
```

Result:

```text
8 passed
```

## Remaining Work

Next highest-value work:

1. Release gate command:
   - minimum success rate
   - maximum newly failed tasks
   - maximum schema violations
   - maximum retry budget exhaustions
2. Failure-only markdown section inside `eval-report.md`.
3. Compare against `latest.json` automatically.
4. Add model/provider configuration snapshots into run manifest.
5. Export trajectory traces for tasks with regressions.
