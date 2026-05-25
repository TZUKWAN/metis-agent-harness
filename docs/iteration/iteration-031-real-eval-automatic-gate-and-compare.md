# Iteration 031 - Real Eval Automatic Gate and Compare

## Purpose

Metis had separate commands for:

- running the real small-model suite
- gating one run
- comparing two runs

That is useful, but continuous harness improvement needs a single command that can run the real suite, write durable artifacts, apply the release gate, and compare against a baseline.

This iteration connects those operations.

## CLI Changes

`metis eval real-small-model` now supports:

```bash
metis eval real-small-model --gate
```

Runs the strict release gate after the current eval report is written.

Default gate output:

```text
docs/evals/runs/<run-name>/gate/
```

```bash
metis eval real-small-model --compare-baseline docs/evals/runs/<baseline>
```

Compares the current run against an explicit baseline.

Default comparison output:

```text
docs/evals/runs/<run-name>/comparison/
```

```bash
metis eval real-small-model --compare-latest
```

Reads the previous `docs/evals/runs/latest.json` before the current run writes a new pointer, then compares the current run against that previous latest run.

Combined usage:

```bash
metis eval real-small-model --gate --compare-latest
```

## Exit Code

The final exit code is `1` if any of these conditions happen:

1. The eval suite does not reach 100% success rate.
2. The release gate fails.
3. Compare detects a regression.
4. `--compare-latest` was requested but no previous latest pointer was available.

Missing endpoint configuration still returns `2` and does not fake model results.

## Tests

Updated:

- `tests/unit/test_cli_eval.py`

New coverage:

- `real-small-model --gate`
- `real-small-model --compare-baseline`
- `real-small-model --compare-latest`
- `--compare-latest` uses the previous latest pointer, not the just-written current run.
- `--compare-latest` fails clearly when no previous latest pointer exists.

Executed:

```bash
python -m pytest -q tests\unit\test_cli_eval.py
python -m compileall -q metis
```

Result:

```text
11 passed
```

## Remaining Work

Next highest-value improvements:

1. Export per-failed-task trace artifacts.
2. Add `--gate-json` / `--compare-json` style machine-readable summaries for combined runs.
3. Add warning thresholds separate from hard-fail thresholds.
4. Add model/provider configuration snapshot into manifest.
5. Add task-level duration and tool-call budget gates.
