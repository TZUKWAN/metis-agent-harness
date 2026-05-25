# Iteration 032 - Failure Artifact Export

## Purpose

Failure-only markdown makes failed eval runs easier to read, but long-term harness improvement needs structured failure samples. Metis should preserve failed tasks as machine-readable artifacts so later tooling can cluster regressions, diagnose failure families, and build targeted repair datasets for small models.

This iteration adds per-failed-task JSON export.

## Change

`EvalSuiteResult.write_reports()` now writes:

```text
failures/index.json
```

for every eval report, even when there are no failures.

When failures exist, it also writes one artifact per failed task:

```text
failures/<safe-task-id>.json
```

Task ids are sanitized before becoming filenames.

## Failure Index

When all tasks pass:

```json
{
  "failure_count": 0,
  "artifacts": []
}
```

When tasks fail, `artifacts` lists:

- task id
- artifact path
- error count

## Failure Artifact Payload

Each failed-task JSON includes:

- task id
- success flag
- status
- turns used
- tool calls
- latency seconds
- core metrics
- schema repair metrics
- tool repair metrics
- retry budget metrics
- trajectory failures
- tool repair counts by type
- tool failure types
- failure shape keys
- errors

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
28 passed
```

## Remaining Work

Next highest-value improvements:

1. Include task prompt/spec metadata in failure artifacts.
2. Include compact tool result excerpts in failure artifacts.
3. Build failure clustering:
   - by failure type
   - by shape key
   - by trajectory error
4. Add a repair recommendation generator based on deterministic failure families.
5. Add model/provider/runtime snapshot to eval manifest.
