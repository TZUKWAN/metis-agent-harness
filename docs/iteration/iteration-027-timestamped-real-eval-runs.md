# Iteration 027 - Timestamped Real Eval Runs

## Purpose

A harness that is improved continuously needs historical eval runs, not only an overwritten `latest` directory. Real small-model behavior changes when prompts, tool feedback, parser repair, and provider models change. Metis therefore needs timestamped run directories and a machine-readable pointer to the most recent run.

## Changes

### Timestamped run names

New helpers:

- `generate_real_small_model_eval_run_name()`
- `resolve_real_small_model_eval_run_name()`
- `real_small_model_eval_runs_root()`
- `real_small_model_eval_latest_pointer_path()`

Supported automatic run-name aliases:

- `auto`
- `timestamp`
- `timestamped`

They resolve to UTC names like:

```text
20260525-010203
```

### CLI default

The real eval CLI now defaults to timestamped runs:

```bash
metis eval real-small-model --workspace . --output-root .
```

Equivalent explicit form:

```bash
metis eval real-small-model --workspace . --output-root . --run-name auto
```

### Latest pointer

Every successful report write now updates:

```text
docs/evals/runs/latest.json
```

The pointer includes:

- suite
- latest run name
- latest run directory
- updated timestamp
- success rate
- task count

### Manifest expansion

Each run's `manifest.json` now includes:

- `run_name`
- `requested_run_name`

This makes it clear whether a directory was explicitly named or resolved from `auto`.

## Tests

Added/updated coverage:

- CLI defaults to `auto`.
- `auto`, `timestamp`, and `timestamped` resolve to stable UTC timestamp names.
- `write_real_small_model_eval_reports(..., run_name="auto")` writes the resolved timestamp directory.
- `latest.json` points to the resolved run directory.

Executed:

```bash
python -m pytest -q tests\unit\test_cli_eval.py tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
```

Result:

```text
8 passed, 3 skipped
```

The skipped tests require real endpoint environment variables and are not faked.

## Remaining Work

The next highest-value eval operations are:

1. Run comparison:
   - current run vs latest previous run
   - current run vs explicitly selected baseline
2. Failure-only markdown summary.
3. Release-gate command with thresholds.
4. Model/provider config snapshot in manifest.
5. Trace export so trajectory-level failures can be inspected outside pytest output.
