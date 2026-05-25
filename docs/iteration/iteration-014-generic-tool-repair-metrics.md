# Iteration 014 - Generic Tool Repair Metrics

Date: 2026-05-25

## Goal

Iteration 013 introduced a unified tool failure taxonomy. This iteration makes the taxonomy measurable across all recoverable tool failures, not just schema validation errors.

For a 9B model, recovery behavior is a core harness metric. The model will make mistakes. The harness must tell us whether those mistakes are:

1. Recoverable.
2. Actually recovered by a later successful tool call.
3. Left unresolved.
4. Concentrated in a specific failure type.

## Changes

### Eval Task Configuration

File: `metis/evals/runner.py`

Added:

- `min_tool_repair_successes`
- `max_tool_repair_failures`
- `allow_recovered_tool_failures`

These are separate from schema-specific gates. A benchmark can now say:

- This task requires at least one successful repair.
- This task allows recovered tool failures to avoid failing the run just because an intermediate mistake was corrected.
- This task allows zero unrecovered tool repair failures.

### Eval Result Metrics

Added:

- `tool_repair_attempts`
- `tool_repair_successes`
- `tool_repair_failures`
- `tool_repair_attempts_by_type`
- `tool_repair_successes_by_type`
- `tool_repair_failures_by_type`

Counting rule:

- A repair attempt is any failed tool result with `recoverable=True`.
- A repair success happens when a later successful call to the same tool appears.
- A repair failure is a recoverable failed tool call with no later successful same-tool call.

### Tool Failure Accounting

`allow_recovered_tool_failures=True` excludes recovered generic tool failures from `tool_failures`. This is opt-in. The default remains strict: a tool failure counts against success unless a benchmark explicitly evaluates recovery behavior.

## Tests

Added tests for:

- Recovered `command_failed` followed by successful `run_test`.
- Unrecovered `command_failed` failing the repair gates.
- Per-type repair dictionaries:
  - `tool_repair_attempts_by_type`
  - `tool_repair_successes_by_type`
  - `tool_repair_failures_by_type`

## Verification

Commands run:

```powershell
python -m pytest -q tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
22 passed in focused eval tests
compileall passed
165 passed, 2 skipped in full test suite
```

## Remaining Risk

The metric currently treats a later successful call to the same tool as recovery. That is strong enough for first-pass evals, but future iterations should improve precision:

1. Match repaired calls by failure type and argument lineage.
2. Track retry budgets per tool and per failure type.
3. Detect unsafe bypass attempts, such as retrying a blocked command through renamed arguments.
4. Add trace events for repair attempts and repair outcomes.
5. Add real-provider evals to verify that 9B/flash models actually respond to the repair instructions.
