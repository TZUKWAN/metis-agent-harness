# Iteration 015 - Tool Repair Retry Budget

Date: 2026-05-25

## Goal

Generic repair metrics reveal whether a model recovers from tool failures, but they do not prevent a small model from repeating the same failed pattern. A 9B model can easily loop on the same broken call if the harness keeps saying the failure is recoverable without enforcing a retry budget.

This iteration adds a runtime retry budget for recoverable tool failures.

## Changes

### Model Profile

File: `metis/runtime/profiles.py`

Added:

- `max_tool_repair_retries`

Current defaults:

- `small`: 1
- `small_strict`: 1
- `balanced`: 2
- `deep`: 4

The smaller the model profile, the tighter the retry budget. This makes sense because small models benefit from explicit stop signals before they drift into loops.

### Agent Loop

File: `metis/runtime/loop.py`

Added `_apply_tool_failure_retry_budget()`.

For every failed tool result with:

- `failure_type`
- `recoverable=True`

the loop now tracks attempts by:

- tool name
- failure type

It adds:

- `repair_attempt_number`
- `max_tool_repair_retries`

When attempts exceed the profile budget, it updates the tool result metadata:

- `retry_allowed=False`
- `retry_budget_exhausted=True`
- replacement `repair_instruction`

The next tool message tells the model not to repeat the same tool call pattern and to choose a different allowed approach or return blocked.

## Tests

Added integration coverage:

- Repeated schema-invalid `write_file` calls under the `small` profile.
- First failure remains retryable.
- Second same-tool/same-failure-type failure exhausts budget.
- Structured tool feedback exposes `retry_allowed=False`.
- ToolResult metadata records `retry_budget_exhausted=True`.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
26 passed in focused tests
compileall passed
166 passed, 2 skipped in full test suite
```

## Remaining Risk

This is a feedback-level retry budget. It does not yet hard-stop a future repeated tool call before dispatch, because the exact failure type is only known after dispatch. Future work should add:

1. Failure lineage that links failed and repaired calls by arguments and error type.
2. Pre-dispatch repeat blocking for exact repeated recoverable failures after budget exhaustion.
3. Separate budgets for safe failures, runtime failures, command failures, and schema failures.
4. Trace events for retry budget state.
5. Real-model evals that confirm small models obey `retry_allowed=False`.
