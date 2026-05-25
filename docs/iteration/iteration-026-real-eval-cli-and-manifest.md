# Iteration 026 - Real Eval CLI and Manifest

## Purpose

Metis needs a repeatable operational loop for real 9B-class model evaluation. Python helper functions are useful for tests, but they are not enough for continuous harness improvement. A production harness needs a command that can be run from a shell, a CI job, or another machine, and that command must leave durable evidence.

This iteration adds the first CLI-facing real eval workflow.

## CLI

New command:

```bash
metis eval real-small-model --workspace . --output-root . --run-name latest
```

Arguments:

- `--workspace`: workspace used by tools and state.
- `--output-root`: root directory where report artifacts are written.
- `--run-name`: report directory name under `docs/evals/runs/`.

Exit codes:

- `0`: eval ran and all tasks passed.
- `1`: eval ran but one or more tasks failed.
- `2`: required real endpoint configuration is missing.

Required endpoint variables:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

When any variable is missing, the CLI refuses to run the real eval and states that no model result was faked.

## Manifest

Stable eval report directories now contain:

- `eval-report.json`
- `eval-report.md`
- `manifest.json`

The manifest records:

- suite
- run name
- generated timestamp
- success rate
- task count
- passed count
- failed count
- metadata
- failed task ids

This gives future comparison tooling a stable input file.

## Tests

Added:

- `tests/unit/test_cli_eval.py`

Updated:

- `tests/e2e/test_local_9b_eval.py`

Executed:

```bash
python -m pytest -q tests\unit\test_cli_eval.py tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
```

Result:

```text
5 passed, 3 skipped
```

The skipped tests require real endpoint environment variables and are not faked.

## Remaining Work

The next operational gaps are:

1. Timestamped run names without manually passing `--run-name`.
2. A `latest` manifest strategy that can point to the most recent timestamped run.
3. A run comparison command:
   - current vs previous success rate
   - newly failed tasks
   - newly introduced schema violations
   - retry-budget regression
   - pre-dispatch block regression
4. Failure-only markdown report section.
5. CI-oriented JSON summary for release gates.
