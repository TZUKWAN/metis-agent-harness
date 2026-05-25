# Iteration 017 - Schema Failure Shape Lineage

Date: 2026-05-25

## Goal

Iteration 016 blocked exact repeated tool calls after retry budget exhaustion. Exact matching is safe, but not enough. A small model can slightly modify irrelevant arguments while preserving the same failure shape.

Example:

```json
{"content": "first"}
{"content": "second"}
{"content": "third"}
```

All three calls still miss `path`. A production harness should recognize that as the same schema failure shape.

This iteration adds argument-shape lineage for schema validation failures.

## Changes

### Agent Loop

File: `metis/runtime/loop.py`

Added:

- `exhausted_shape_fingerprints`
- `_tool_failure_shape_key()`
- `_predict_schema_failure_shape_key()`

For `schema_validation_failed`, the shape key is:

```text
(tool_name, "schema_validation_failed", "|".join(schema_errors))
```

When a schema failure exceeds retry budget, the loop stores this shape key. Later calls are checked before dispatch by running the schema validator against the proposed arguments. If the same schema error shape appears again, the call is blocked before dispatch with:

- `failure_type=retry_budget_exhausted`
- `original_failure_type=schema_validation_failed`
- `retry_allowed=False`
- `failure_shape_key`

## Tests

Added integration coverage:

- Repeated `write_file` calls with different `content` values but the same missing `path`.
- Under the `small` profile, the second failed shape exhausts budget.
- The third same-shape call is blocked as `retry_budget_exhausted`.
- The result includes `failure_shape_key=$.path: missing required property`.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
28 passed in focused tests
compileall passed
168 passed, 2 skipped in full test suite
```

## Remaining Risk

This only covers schema failure shapes. Future lineage work should cover:

1. Command semantic lineage, such as equivalent destructive or failing commands.
2. Runtime exception lineage, such as same exception type and message with lightly changed arguments.
3. Allowlist violation lineage, such as repeatedly attempting forbidden tools.
4. Cross-tool bypass lineage, such as trying `run_shell` after `run_command` is blocked for the same operation.
