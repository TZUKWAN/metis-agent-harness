# Iteration 049 - Eval Repair Plan

## Goal

Iteration 048 turned comparison diagnosis into repair task stubs. That still left an operator with a flat queue. This iteration adds a second planning layer so Metis can organize repair tasks by release risk, owner area, and execution phase.

For a 9B-class model harness, this matters because weak models need a strong external improvement loop. The harness should not merely say that something regressed; it should convert the regression into an ordered fix queue that can be reviewed, implemented, covered by evals, and checked again.

## Implemented

1. Added repair task loading:
   - `load_repair_tasks(path)`
   - accepts either a `repair-tasks.json` file or a directory containing it.

2. Added repair plan construction:
   - `build_repair_plan(repair_tasks)`
   - sorts tasks by priority, owner area, and task id.
   - groups tasks into priority buckets.
   - groups tasks by owner area.
   - collects related cluster keys.
   - collects recommended actions and suggested evals.
   - creates execution phases.
   - emits next actions.

3. Added repair plan rendering and persistence:
   - `repair_plan_to_markdown(plan)`
   - `write_repair_plan(plan, output_dir)`
   - writes `repair-plan.json`
   - writes `repair-plan.md`

4. Added one-call planning helper:
   - `plan_repairs(repair_tasks_path, output_dir=None)`

5. Added CLI command:
   - `metis eval repair-plan --repair-tasks <repair-tasks.json-or-dir>`
   - `metis eval repair-plan --repair-tasks <repair-tasks.json-or-dir> --output-dir <plan-dir>`
   - `metis eval repair-plan --repair-tasks <repair-tasks.json-or-dir> --json`

6. Added tests:
   - plan grouping by priority and owner area.
   - plan file loading and writing.
   - repair-plan markdown rendering.
   - CLI markdown output.
   - CLI JSON output.

## Repair Plan Schema

The generated plan contains:

- `profile`
- `baseline`
- `current`
- `task_count`
- `tasks`
- `priority_buckets`
- `owner_areas`
- `phases`
- `next_actions`

Priority buckets currently use:

- `critical`
- `high`
- `medium`
- `low`

Execution phases currently use:

1. `phase-1-stop-release-blockers`
2. `phase-2-add-targeted-evals`
3. `phase-3-stabilize-owners`

## Why This Improves The Harness

Current agent observability and eval practice increasingly treats trace failures as work items rather than static logs. Useful systems connect failures to span-level evidence, group them into recurring failure families, and open concrete repair work. This iteration moves Metis further in that direction:

1. comparison detects quality movement;
2. diagnosis extracts action-oriented regression entries;
3. repair tasks create fix stubs;
4. repair plan organizes those stubs into a queue;
5. future iterations can attach trace spans and targeted evals to each queued task.

This is especially important for small models. A small model should not be trusted to decide whether its own failure was important, where the root cause lives, or what order repairs should happen in. Metis now makes that ordering deterministic at the harness layer.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
```

Result:

```text
41 passed
```

## Remaining Gaps

The next highest-value gaps are:

1. Trace timeline export:
   - repair tasks should point to a concrete step, tool call, schema repair, gate decision, or finalization attempt.

2. Repair task source mapping:
   - repair tasks should map to likely Metis source modules, not just owner areas.

3. Targeted eval generation:
   - repair tasks should be convertible into new eval task stubs.

4. Repair verification loop:
   - after a fix, Metis should rerun only the affected eval slice first, then the full release gate.

5. Human review state:
   - repair plans should carry status such as `open`, `in_progress`, `fixed`, `verified`, and `deferred`.
