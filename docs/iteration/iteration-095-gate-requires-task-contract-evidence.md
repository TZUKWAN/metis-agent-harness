# Iteration 095: Gate Requires Task Contract Evidence

Date: 2026-05-25

## Objective

Iteration 093 wrote task contract identity into eval artifacts. Iteration 094 made comparison consume that identity. This iteration makes release gating enforce it.

Before this change, `metis eval gate --run <run-dir>` required suite schema evidence, but it could still pass a run that had no top-level task contract evidence. That left a provenance gap: the gate could prove the suite schema contract, but not the exact task contract set used for the run.

## Completed Changes

1. `evaluate_eval_run_gate()` now requires task contract evidence by default:
   - `task_contract_hash`
   - non-empty `task_spec_hash_summary`

2. Missing task contract evidence now produces explicit gate failures:
   - `task_contract_hash missing from manifest`
   - `task_spec_hash_summary missing from manifest`

3. The gate result now records:
   - `require_task_contract_evidence`
   - `run.task_contract_hash`
   - `run.task_spec_hash_summary`

4. Gate Markdown now renders:
   - `Task contract hash`
   - `Task spec hash summary count`

5. CLI `metis eval gate --run ...` explicitly passes:
   - `require_suite_schema_evidence=True`
   - `require_task_contract_evidence=True`

6. Python API keeps a legacy analysis escape hatch:

```python
evaluate_eval_run_gate(run_dir, require_task_contract_evidence=False)
```

The CLI remains strict because release usage should not silently accept incomplete provenance.

## Why This Matters

For a 9B/flash-model harness, release gating must protect against two classes of false confidence:

1. The model passed because the task contract changed or weakened.
2. The run artifact was copied, assembled, or generated without enough identity to prove what was evaluated.

Schema evidence proves the suite file/runtime contract. Task contract evidence proves the actual tasks and constraints. A release gate should require both.

## Verification

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - `48 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py -q`
  - `136 passed`
- `python -m pytest -q`
  - `333 passed, 4 skipped`

## Remaining Gaps

1. Build a combined provenance hash over suite schema hash, task contract hash, model profile, and tool inventory hash.
2. Add gate checks for combined provenance evidence once the hash exists.
3. Generate pre-run contract artifacts for code-defined suites before real provider calls.
4. Teach `eval diagnose` to produce an explicit task-contract-drift review task.
