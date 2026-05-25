# Iteration 133 - Artifact Path Hygiene Repair Phase

Date: 2026-05-25

## Problem

Iteration 132 made `artifact_path_hygiene_failed` a release/strict regression reason.

That was necessary but not sufficient. A repair plan can still be misleading if it begins with ordinary behavior work while the eval contract itself contains non-portable artifact metadata. Absolute paths, Windows drive-prefixed paths, and parent traversal are not model behavior failures. They are suite hygiene failures.

For a scenario-agnostic harness, repair ordering must preserve causality:

1. verify artifact trust;
2. repair invalid suite and contract metadata;
3. repair model behavior regressions;
4. add targeted eval coverage;
5. stabilize owner areas.

Without that ordering, a 9B model can waste repair attempts on symptoms created by bad harness metadata.

## Implementation

`build_repair_plan()` now detects repair tasks whose reason is:

```text
artifact_path_hygiene_failed
```

When such a task exists, the plan includes a new pre-behavior phase:

```text
phase-0b-repair-suite-hygiene
```

The phase is inserted after `phase-0-restore-artifact-trust` when artifact trust repair is also present, and before `phase-1-stop-release-blockers` in all cases.

The phase metadata is:

- title: `Repair suite hygiene`
- description: remove non-portable artifact paths and invalid eval contract metadata before repairing model behavior
- task ids: every repair task with reason `artifact_path_hygiene_failed`

The same task can still appear in later planning views when appropriate:

- `phase-2-add-targeted-evals` if it has a suggested eval;
- `phase-3-stabilize-owners` if it is medium/low priority;
- owner area summaries under `eval-suite-hygiene`.

That preserves both causal ordering and owner accountability.

## Harness Impact

This iteration makes repair planning more faithful to how a real harness should operate.

Artifact path hygiene is not just another quality gate failure. It is a contract hygiene problem that can invalidate downstream comparisons and generated suites. Putting it in a pre-behavior phase gives Metis a stronger loop:

1. compare identifies non-portable path metadata;
2. regression reasons classify it as `artifact_path_hygiene_failed`;
3. repair tasks route it to `eval-suite-hygiene`;
4. repair plans schedule it before model behavior repair;
5. targeted evals can lock the hygiene rule in place.

This is especially important for 9B models because small models need the harness to remove ambiguous failure causes. If the suite contract is dirty, a small model may overfit the bad local path or misdiagnose a contract issue as a reasoning failure.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
```

Result:

```text
56 passed
```

New test coverage verifies:

1. suite hygiene phase appears before release blockers;
2. `artifact_path_hygiene_failed` tasks enter `phase-0b-repair-suite-hygiene`;
3. ordinary high-priority behavior regressions remain release blockers;
4. hygiene tasks still appear in targeted eval and owner-area phases when applicable;
5. artifact trust remains earlier than suite hygiene when both preconditions exist.

## Remaining Work

1. Add configurable severity thresholds for artifact path hygiene diagnostics.
2. Add dashboard rendering for the new suite hygiene phase.
3. Add repair-plan export metadata that marks pre-behavior phases as hard preconditions.
4. Add run-to-run trend comparison for artifact path diagnostics.
5. Add real small-model eval cases that intentionally produce path hygiene failures.
