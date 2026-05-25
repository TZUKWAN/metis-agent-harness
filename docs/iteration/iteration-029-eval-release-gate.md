# Iteration 029 - Eval Release Gate

## Purpose

Metis now has real eval runs and run comparison. The next required operational layer is release gating: a command that can be used by CI, local release scripts, or manual audits to reject a run that does not meet production thresholds.

This iteration adds deterministic gate checks for one eval run directory.

## New Module

Added:

```text
metis/evals/gate.py
```

Public helpers:

- `evaluate_eval_run_gate(run_dir, ...)`
- `eval_gate_to_markdown(gate)`
- `write_eval_gate_report(gate, output_dir)`
- `DEFAULT_GATE_THRESHOLDS`

## CLI

New command:

```bash
metis eval gate --run docs/evals/runs/<run-name>
```

Optional:

```bash
metis eval gate \
  --run docs/evals/runs/<run-name> \
  --output-dir docs/evals/gates/<name> \
  --json
```

Exit codes:

- `0`: gate passed.
- `1`: gate failed.

## Default Thresholds

The default gate is intentionally strict:

- `min_success_rate=1.0`
- `max_failed_tasks=0`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`
- `max_trajectory_failures=0`

These defaults align with the goal of making 9B-class models reliable through harness constraints. A weaker model is allowed to be smaller, but the harness should not quietly tolerate invalid tool calls, schema errors, retry-budget exhaustion, or trajectory failures.

## Gate Outputs

When `--output-dir` is provided, Metis writes:

- `gate.json`
- `gate.md`

Gate payload:

- run summary
- pass/fail status
- thresholds
- aggregated negative metrics
- failed task ids
- human-readable failure list

## Tests

Added:

- `tests/unit/test_eval_gate.py`

Updated:

- `tests/unit/test_cli_eval.py`

Executed:

```bash
python -m pytest -q tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py
python -m compileall -q metis
```

Result:

```text
10 passed
```

## Remaining Work

Next highest-value improvements:

1. Failure-only markdown section in normal eval reports.
2. Gate comparison mode:
   - fail if current run regresses against baseline
   - combine `eval compare` and `eval gate`
3. Automatic gate after `metis eval real-small-model`.
4. Trace artifact export for gated failures.
5. Separate warning thresholds from hard-fail thresholds.
