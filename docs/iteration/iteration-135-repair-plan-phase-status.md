# Iteration 135 - Repair Plan Phase Status

Date: 2026-05-25

## Problem

Iteration 134 made repair-plan preconditions machine-readable, but it did not yet tell automation whether a phase is currently executable.

A repair executor needs more than:

- phase order;
- hard precondition markers;
- dependency lists.

It also needs:

- current phase status;
- blocked-by relationships;
- top-level status summary;
- a list of executable phases.

Without this, a future CLI or agent executor would still need to reimplement precondition logic outside the plan. That increases the risk that a 9B model tries to repair behavior while artifact trust or suite hygiene is still unresolved.

## Implementation

Repair plans now annotate every phase with:

- `status`
- `blocked_by`

Task status is normalized from repair task metadata:

- `verified` remains `verified`;
- `complete`, `completed`, and `done` become `complete`;
- `in_progress` and `running` become `in_progress`;
- `blocked` and `failed` become `blocked`;
- missing or unknown status becomes `open`;
- `not_applicable` and `skipped` become `not_applicable`.

Phase status is derived from task status and hard-precondition dependencies:

1. phases with no tasks are `not_applicable`;
2. phases whose required hard preconditions are incomplete are `blocked`;
3. phases whose tasks are all complete/verified are `complete` or `verified`;
4. phases with running tasks are `in_progress`;
5. phases with blocked/failed tasks are `blocked`;
6. all other task-bearing phases are `open`.

The plan now also includes:

```json
{
  "phase_status_summary": {
    "counts": {},
    "blocked_phases": [],
    "executable_phases": [],
    "hard_preconditions_open": []
  }
}
```

Markdown rendering now prints:

- phase status;
- blocked-by list;
- phase status summary.

## Harness Impact

This closes the gap between "ordered repair plan" and "executor-ready repair plan."

For a strong harness around weak models, the control plane should not rely on the model to infer what is safe to do next. The plan itself now says:

1. which preconditions are still open;
2. which phases are blocked;
3. which phases are executable now;
4. when downstream behavior repair may proceed.

This is a direct harness improvement for 9B models because it removes another class of orchestration judgment from the model and puts it into deterministic infrastructure.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
```

Result:

```text
57 passed
```

New coverage verifies:

1. an open suite hygiene precondition blocks release blocker, targeted eval, and owner stabilization phases;
2. blocked phases carry `blocked_by`;
3. the top-level summary lists blocked phases and executable phases;
4. verified preconditions unblock downstream phases;
5. Markdown renders status and blocked-by metadata.

## Remaining Work

1. Add CLI enforcement that refuses to execute non-executable phases.
2. Add repair-plan phase status persistence updates after each repair attempt.
3. Add dashboard rendering for blocked phase chains.
4. Add repair-plan attestation over status and dependency metadata.
