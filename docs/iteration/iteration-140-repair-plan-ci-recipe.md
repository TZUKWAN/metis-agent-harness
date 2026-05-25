# Iteration 140 - Repair Plan CI Recipe

Date: 2026-05-25

## Problem

Iterations 136-139 added the mechanics for safe repair-plan enforcement:

- phase executability;
- hard precondition blocking;
- repair-plan attestation;
- attestation verification;
- CLI phase enforcement.

The missing piece was a single documented CI recipe that shows the correct command order.

Without that recipe, a user or future automation could run the right commands in the wrong order. For example, it could enforce a phase before verifying the plan artifact, or invoke model repair work before hard preconditions are clear.

## Implementation

Added:

```text
docs/evals/repair-plan-ci-recipe.md
```

The recipe defines the standard sequence:

1. `metis eval compare`
2. `metis eval diagnose`
3. `metis eval repair-plan`
4. `metis eval verify-repair-plan`
5. `metis eval repair-plan --require-executable-phase <phase-id>`

It also documents:

- required inputs;
- expected artifacts;
- hard precondition phases;
- recommended CI policy;
- why model calls must remain downstream of deterministic trust checks.

The 9B eval report now links to the recipe.

Added a documentation regression test:

```python
test_repair_plan_ci_recipe_covers_verified_phase_workflow
```

The test locks the recipe to the important commands and safety claims:

- compare;
- diagnose;
- repair-plan;
- verify-repair-plan;
- phase enforcement;
- repair-plan attestation;
- artifact trust precondition;
- suite hygiene precondition;
- never invoke a model on a blocked phase;
- never invoke a model from an unattested repair plan.

## Harness Impact

The repair flow is now not only implemented but operationalized.

For a harness that should let 9B models perform higher-quality work, this matters because small models benefit from a strict outer control loop:

1. prove artifacts are trustworthy;
2. prove the repair plan is trustworthy;
3. prove the selected phase is executable;
4. only then invoke model or infrastructure repair work.

The recipe makes that control loop reproducible by humans, CI systems, and future agent executors.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_docs_exist.py -q
```

Result:

```text
3 passed
```

## Remaining Work

1. Add a dedicated repair execution command that consumes the same verified phase workflow.
2. Add attestation for targeted eval stubs and materialized suites.
3. Add signed attestation support.
4. Add CI examples for GitHub Actions and local PowerShell scripts.
