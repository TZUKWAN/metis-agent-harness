# Iteration 094: Compare Task Contract Hash Drift

Date: 2026-05-25

## Objective

Iteration 093 wrote `task_contract_hash` and `task_spec_hash_summary` into run manifests and latest pointers. This iteration makes `eval compare` consume that top-level evidence directly.

Before this change, compare could detect per-task drift from `task-specs.json` or failure artifacts, but it did not report a suite-level task contract hash change from `manifest.json`.

## Completed Changes

1. `compare_eval_runs()` now passes manifest-derived task contract hashes into task spec diffing.
2. `_task_spec_hash_summary()` now prefers `task_spec_hash_summary` from `task-specs.json` when present, falling back to the older per-task list format.
3. `_task_contract_hash()` reads:
   - `manifest.json.task_contract_hash` first;
   - `task-specs.json.task_contract_hash` as fallback.
4. `task_spec_diff` now includes:
   - `baseline_task_contract_hash`
   - `current_task_contract_hash`
   - `task_contract_hash_changed`
5. Comparison Markdown now renders:
   - `Task contract hash changed`
6. Strict compare profile now treats task contract hash drift as a regression reason:
   - `task_contract_hash_changed`
7. Regression reason links now include the hash drift payload.

## Why This Matters

For 9B/flash model regression work, task contract drift must be visible before model behavior is interpreted. If the prompt, required tool set, evidence requirement, finalization gate, or schema repair requirement changes, then a behavior difference may be caused by the eval contract rather than the model or runtime.

This iteration makes that distinction visible in the top-level comparison output.

## Verification

- `python -m pytest tests\unit\test_eval_compare.py -q`
  - `39 passed`
- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - `134 passed`
- `python -m pytest -q`
  - `331 passed, 4 skipped`
- `python -m compileall -q metis`
  - passed

## Remaining Gaps

1. `eval gate` should require non-empty task contract evidence in release mode.
2. `eval diagnose` should create a dedicated repair task when task contract drift is present.
3. Comparison should eventually include a combined provenance hash over suite schema hash, task contract hash, model profile, and tool inventory hash.
4. The real-small-model path should emit a pre-run code-defined suite contract artifact before spending model tokens.
