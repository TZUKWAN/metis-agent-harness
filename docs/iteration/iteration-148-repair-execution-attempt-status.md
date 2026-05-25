# Iteration 148 - Repair Execution Attempt Status

## Problem

`repair-execute` had become a verified preflight gate, but it still stopped at readiness. The remaining harness gap was status persistence:

- a future executor could know that a phase was ready;
- but the repair plan had no durable attempt status;
- task and phase state could not be resumed from a new snapshot.

## Change

`metis eval repair-execute` now supports:

```text
--record-attempt-status in_progress|blocked|complete|verified
--executor-id <id>
--attempt-note <text>
```

Attempt recording requires `--output-dir`.

It writes:

- `repair-execute-attempt/repair-execute-attempt.json`
- `repair-execute-attempt/repair-execute-attempt.md`
- `updated-repair-plan/repair-plan.json`
- `updated-repair-plan/repair-plan.md`
- `updated-repair-plan/repair-plan-attestation.json`
- `updated-repair-plan/repair-plan-attestation.md`

If preflight is not ready, the persisted attempt status is forced to `blocked`.

## Updated Plan Semantics

The updated repair plan:

1. marks all tasks in the selected phase with the recorded status;
2. attaches `last_attempt` to affected tasks;
3. attaches `last_attempt` to the selected phase;
4. regenerates phase status through `build_repair_plan()`;
5. appends a top-level `execution_attempts` summary;
6. writes a fresh repair-plan attestation.

## Why This Matters

Metis is a harness, not a domain-specific auto-fixer. This iteration does not pretend to repair arbitrary business logic. It creates the durable control-plane layer a real repair executor needs:

- verified readiness;
- recorded executor identity;
- explicit status;
- immutable attempt artifact;
- updated and attested repair-plan snapshot.

This keeps the 9B model downstream of deterministic state management and makes resume/retry behavior auditable.

## Verification

Focused validation for this iteration should include:

```powershell
python -m compileall -q metis
python -m pytest tests\unit\test_docs_exist.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py tests\unit\test_run_attestation.py -q
```
