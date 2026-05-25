# Iteration 019 - Lineage Eval Metrics

Date: 2026-05-25

## Goal

Iterations 016-018 added runtime controls for repeat blocking and failure shape lineage. Those controls are useful only if eval reports can expose them. Real 9B model testing needs to answer:

1. Is the model repeatedly hitting retry budgets?
2. Are blocks happening before dispatch or only after tool execution?
3. Which failure shapes are dominating?
4. Is the loop protection correcting behavior or hiding a deeper prompt/tool design problem?

This iteration adds lineage metrics to EvalRunner.

## Changes

### Agent Loop

File: `metis/runtime/loop.py`

Pre-dispatch retry-budget blocks now include:

- `pre_dispatch_block=True`

Structured tool feedback already includes `failure_shape_key` when available.

### Eval Result

File: `metis/evals/runner.py`

Added:

- `retry_budget_exhaustions`
- `pre_dispatch_blocks`
- `failure_shape_keys`

Definitions:

- `retry_budget_exhaustions`: count of tool results where `retry_budget_exhausted=True`.
- `pre_dispatch_blocks`: count of tool results blocked before dispatcher execution.
- `failure_shape_keys`: frequency table of observed failure shape keys.

The markdown report now includes:

- Retry Budget Exhaustions
- Pre-dispatch Blocks

The JSON report includes all new fields through the existing dataclass serialization.

## Tests

Added an EvalRunner test that runs a real AgentLoop sequence:

1. `run_test("python -m pytest tests/a.py")` fails.
2. `run_test("python -m pytest tests/b.py")` fails and exhausts budget.
3. `run_test("python -m pytest tests/c.py")` is blocked before dispatch because it has the same semantic shape: `python pytest`.

Assertions verify:

- `retry_budget_exhaustions == 2`
- `pre_dispatch_blocks == 1`
- `tool_failure_types["command_failed"] == 2`
- `tool_failure_types["retry_budget_exhausted"] == 1`
- `failure_shape_keys["python pytest"] == 3`

## Verification

Commands run:

```powershell
python -m pytest -q tests\unit\test_eval_runner.py tests\integration\test_agent_loop_schema_guard.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
31 passed in focused tests
compileall passed
171 passed, 2 skipped in full test suite
```

## Remaining Risk

The lineage metrics are now visible, but there are no eval gates yet for them. Future iterations should add:

1. `max_retry_budget_exhaustions`
2. `max_pre_dispatch_blocks`
3. required/forbidden failure shape keys
4. per-tool failure-shape thresholds
5. dashboard/report sections that list top failure shapes by model and task
