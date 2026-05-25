# Iteration 091: Gate Requires Suite Schema Evidence

Date: 2026-05-25

## Objective

Iteration 089 made `metis eval run-suite --gate` reject unversioned suites before model execution. Iteration 090 then wrote suite schema snapshot metadata into generic eval metadata, run `manifest.json`, and `latest.json`.

The remaining gap was the independent release gate path:

```bash
metis eval gate --run docs/evals/runs/<run-name>
```

Before this iteration, that command evaluated task outcomes and aggregate failure artifacts, but it did not prove that the run manifest itself carried suite schema evidence. That meant an old or manually assembled run directory could still pass release gating without declaring which suite schema artifact governed the run.

## Completed Changes

1. `evaluate_eval_run_gate()` now requires suite schema evidence by default:
   - `suite_schema_id`
   - `suite_schema_sha256`

2. Missing manifest evidence now produces explicit gate failures:
   - `suite_schema_id missing from manifest`
   - `suite_schema_sha256 missing from manifest`

3. The gate result now records:
   - `require_suite_schema_evidence`
   - `run.suite_schema_id`
   - `run.suite_schema_sha256`

4. Gate markdown now renders the suite schema id and hash so a reviewer can audit the run without opening `manifest.json`.

5. CLI `metis eval gate --run ...` explicitly passes `require_suite_schema_evidence=True`. This makes the command-line release path strict even if the library default is changed later.

6. A programmatic escape hatch exists for legacy analysis:

```python
evaluate_eval_run_gate(run_dir, require_suite_schema_evidence=False)
```

This is intentionally not exposed as the default CLI behavior. Release gating should be strict; legacy inspection can be done through the Python API when there is a conscious reason.

## Why This Matters

The harness is being built as reusable infrastructure for many future agents and scenario-specific systems. Eval artifacts must therefore be self-proving. A passing gate should not only say “the tasks passed”; it should also prove which schema contract defined the suite that generated those results.

For small 9B/flash models, this matters because most quality failures come from contract drift:

- suite files using fields the runtime no longer understands;
- suite files missing fields that newer gates rely on;
- historical runs being compared against newer expectations;
- manually copied run folders losing validation context;
- downstream release decisions trusting incomplete artifacts.

This iteration closes that artifact-chain gap:

```text
suite-schema-v1.json
-> suite validation report
-> suite metadata
-> run manifest
-> latest pointer
-> independent release gate
```

## Tests Added

1. Gate fails when manifest suite schema evidence is missing.
2. Gate can be relaxed programmatically for legacy run inspection.
3. CLI gate passes `require_suite_schema_evidence=True`.
4. Markdown report renders the suite schema hash.

## Verification

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - `46 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py -q`
  - `108 passed`
- `python -m pytest -q`
  - `326 passed, 4 skipped`

## Remaining Gaps

1. The real-small-model suite path still needs an explicit manifest schema evidence strategy or a documented non-loadable-suite declaration.
2. Suite version migration errors still need dedicated exception types and diagnostic codes.
3. Suite-level `tool_schemas` should be designed so a suite can declare a local schema catalog instead of repeating schemas per task.
4. Suite-local tool schema legality checks should be expanded beyond the current basic structural validation.
5. Gate reports can still become more provenance-rich by including validation report path/hash when available.
