# Iteration 030 - Failure-only Eval Report

## Purpose

Metis already records detailed eval metrics, but a large markdown table is not enough when a real endpoint run fails. The operator needs a direct failure section with errors, failure types, and shape keys. This is especially important for small-model harness work because failures often come from tool schema drift, repeated bad repair attempts, or trajectory mistakes rather than final-answer wording.

This iteration adds a failure-only section to `eval-report.md`.

## Change

`EvalSuiteResult.to_markdown()` now appends:

```text
## Failure Details
```

If every task passes:

```text
- None
```

If tasks fail, only failing tasks are expanded. Each failed task includes:

- status
- turns used
- tool calls
- parser failures
- tool failures
- quality failures
- invalid tool calls
- schema violations
- retry budget exhaustions
- pre-dispatch blocks
- trajectory failures
- tool failure types
- failure shape keys
- errors

## Why It Matters

The release gate can reject a run, but the human still needs to know why. The failure-only section turns the eval markdown into a practical debugging artifact:

1. It preserves the full aggregate table.
2. It avoids forcing reviewers to scan passing tasks.
3. It exposes the exact failure signals used by compare and gate.
4. It makes repeated small-model failure patterns visible.

## Tests

Updated:

- `tests/unit/test_eval_runner.py`

Executed:

```bash
python -m pytest -q tests\unit\test_eval_runner.py
python -m compileall -q metis
```

Result:

```text
27 passed
```

## Remaining Work

Next highest-value improvements:

1. Automatically run gate after real eval:
   - `metis eval real-small-model --gate`
2. Automatically compare against previous latest:
   - `metis eval real-small-model --compare-latest`
3. Export per-failure trace artifacts:
   - tool calls
   - tool results
   - structured feedback
   - evidence refs
4. Add warning thresholds distinct from hard-fail thresholds.
