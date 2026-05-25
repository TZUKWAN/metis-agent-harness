# Iteration 016 - Failure Lineage and Pre-dispatch Repeat Blocking

Date: 2026-05-25

## Goal

Iteration 015 added retry budgets for recoverable tool failures, but the budget was still feedback-only. If a small model ignored `retry_allowed=False`, the next identical call could still enter the dispatcher.

This iteration adds failure lineage and pre-dispatch repeat blocking:

1. Recoverable failed tool calls get a lineage key based on tool name and canonicalized arguments.
2. When a retry budget is exhausted, the lineage key is marked as exhausted.
3. Later identical tool calls are blocked before dispatcher execution.
4. The model receives a structured `retry_budget_exhausted` tool result.

This matters for 9B models because they often repeat a previous failed action verbatim. The harness should not rely only on the model obeying text instructions.

## Changes

### Failure Taxonomy

File: `metis/tools/failures.py`

Added:

- `ToolFailureType.RETRY_BUDGET_EXHAUSTED`

This failure type is non-recoverable. It tells the model:

- the same tool call pattern is no longer allowed;
- it must choose a materially different approach or return blocked.

### Agent Loop

File: `metis/runtime/loop.py`

Added:

- `exhausted_retry_fingerprints`
- `_tool_call_lineage_key()`
- `_maybe_block_exhausted_tool_retry()`

Lineage key:

```text
(tool_name, json.dumps(arguments, sort_keys=True))
```

When a recoverable failure exceeds `max_tool_repair_retries`, the loop stores the lineage key. On a later identical call, the loop returns a blocked `ToolResult` before dispatching the tool.

The blocked result includes:

- `failure_type=retry_budget_exhausted`
- `original_failure_type`
- `retry_budget_exhausted=True`
- `retry_allowed=False`
- `failure_lineage_key`

## Tests

Added integration coverage:

- A fragile tool raises `RuntimeError` for the same arguments.
- Under the `small` profile, the second same failure exhausts the retry budget.
- A third identical call is blocked before handler execution.
- Handler call count proves pre-dispatch blocking worked.
- Structured feedback exposes `error_type=retry_budget_exhausted`.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py tests\unit\test_tools.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
37 passed in focused tests
compileall passed
167 passed, 2 skipped in full test suite
```

## External Reference

OpenAI Agents SDK documents tool guardrails as invocation-level checks that can reject a tool call with a message before execution. This supports the Metis direction: runtime control should happen around each tool invocation, not only at final output validation.

Reference: https://openai.github.io/openai-agents-js/guides/guardrails

## Remaining Risk

The lineage key is intentionally exact-match. That is safe, but still weak against disguised repeats. Future iterations should add:

1. Argument-shape fingerprints that ignore irrelevant fields.
2. Semantic equivalence checks for dangerous commands.
3. Per-failure-type lineage policies.
4. Trace events for exhausted lineage keys.
5. Real-model evals that verify 9B models switch strategy after receiving `retry_budget_exhausted`.
