# Iteration 055 - Targeted Eval Stubs

## Goal

Repair tasks and repair plans now identify failure reasons, artifacts, timelines, critical events, owner areas, and likely source modules. The next missing link was verification: every repair should suggest a focused eval or test slice before the fix is accepted.

This iteration adds targeted eval stub generation from repair tasks.

## Implemented

1. Added targeted eval stub generation:
   - `build_eval_stubs_from_repair_tasks(repair_tasks)`

2. Added targeted eval stub rendering:
   - `eval_stubs_to_markdown(stubs)`

3. Added targeted eval stub persistence:
   - `write_eval_stubs(stubs, output_dir)`
   - writes `targeted-eval-stubs.json`
   - writes `targeted-eval-stubs.md`

4. Added CLI command:
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir>`
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir> --output-dir <stubs-dir>`
   - `metis eval eval-stubs --repair-tasks <repair-tasks-json-or-dir> --json`

5. Eval stubs include:
   - source repair task id;
   - reason;
   - priority;
   - owner area;
   - cluster keys;
   - critical event ids;
   - likely source modules;
   - suggested assertion;
   - verification command;
   - eval task spec skeleton.

6. Eval task spec skeletons currently adapt constraints for:
   - schema failures;
   - retry/failure-shape failures;
   - evidence/finalization failures;
   - parser failures;
   - generic trajectory failures.

## Why This Matters

This pushes Metis closer to a closed improvement loop:

1. run eval;
2. compare against baseline;
3. diagnose regression;
4. generate repair tasks;
5. generate repair plan;
6. generate targeted eval stubs;
7. implement fix;
8. run focused verification;
9. run full release gate.

For 9B-class models, this structure is the harness doing the hard work. The model should receive a specific failing boundary, likely modules, and verification contract rather than being asked to infer everything from a large failure report.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
```

Result:

```text
47 passed
```

## Remaining Gaps

1. Eval stubs are not yet executable `EvalTaskSpec` files.

2. The generated prompt is still generic and should later include minimized reproduction context.

3. Verification commands are rule-based and should incorporate actual changed files when git history is available.

4. The eval-stub workflow should eventually support automatic insertion into a suite under review.
