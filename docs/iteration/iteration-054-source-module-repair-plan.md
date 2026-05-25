# Iteration 054 - Source Module Repair Plan

## Goal

Repair tasks already link to artifacts, timelines, event ids, and critical events. The remaining operator gap was source localization: the plan still did not say which Metis modules are likely responsible for a failure family.

This iteration adds deterministic source-module mapping and exposes critical events and likely modules at the repair-plan owner-area level.

## Implemented

1. Repair task generation now adds:
   - `likely_source_modules`

2. Source-module mapping currently uses:
   - regression reason;
   - cluster keys;
   - regressed metric names;
   - remediation backlog owner area.

3. Initial source-module rules cover:
   - schema failures;
   - policy/approval/command failures;
   - retry/lineage/failure-shape failures;
   - evidence/finalization failures;
   - parser repair failures;
   - trajectory/task-constraint failures;
   - task spec/environment drift.

4. Repair plan owner-area summaries now include:
   - `critical_event_ids`
   - `likely_source_modules`

5. Repair plan markdown now renders:
   - critical events by owner area;
   - likely source modules by owner area.

## Why This Matters

This iteration makes the repair loop more operational:

1. failure comparison identifies regression;
2. diagnosis extracts reason and artifacts;
3. repair task links timelines and critical events;
4. repair task now suggests likely source modules;
5. repair plan aggregates those suggestions by owner area.

For a 9B-class model, this is a harness advantage. The smaller model should not need to infer from scratch whether a schema failure belongs in dispatcher, schema validator, runtime loop, or eval oracle code. Metis now provides deterministic source hints before any model-assisted repair.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
```

Result:

```text
43 passed
```

## Remaining Gaps

1. Source-module mapping should be extracted into its own module once more rules are added.

2. Source-module mapping should read actual changed files when a git baseline is available.

3. Repair plan phases should include verification commands per likely source module.

4. Repair tasks should generate targeted eval stubs automatically.

5. Future OTel export should map critical event ids to span ids and source modules.
