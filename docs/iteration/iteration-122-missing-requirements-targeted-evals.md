# Iteration 122 - Missing Requirements in Targeted Evals

This iteration carries requirement coverage gaps into targeted eval stubs and materialized suites.

## Problem

Iteration 121 made `requirements_covered` emit structured `missing_requirements` metadata.

That metadata still lived inside `quality_gate_changes`. A 9B model should not have to infer acceptance criteria from nested gate metadata or a prose failure message. Requirement gaps need to become first-class targeted eval context.

## Changes

1. Added extraction for missing requirements from quality gate metadata.
2. Targeted eval stubs now preserve:
   - `missing_requirements`
3. Materialized targeted suite wrappers now preserve:
   - `missing_requirements`
4. Stub Markdown and suite Markdown now render missing requirements.
5. Targeted eval prompts now include a dedicated requirement coverage context:
   - the previously missing requirements are listed exactly;
   - the repair is incomplete unless final output or recorded evidence makes each requirement verifiable.
6. Suite schema documentation now includes `missing_requirements` as wrapper metadata.

## Why This Matters

Requirement coverage is a core harness responsibility.

When a small model fails to cover acceptance criteria, the harness should not hand it a vague failure sentence. It should pass the exact uncovered requirements into the next regression task.

The path is now:

```text
requirements_covered gate fails
-> missing_requirements metadata
-> comparison quality_gate_diff
-> repair task quality_gate_changes
-> targeted eval missing_requirements
-> prompt-level requirement coverage context
```

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `51 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Add a dedicated `requirements` field to `EvalTaskSpec` so targeted eval runtime can feed requirements directly into `requirements_covered`.
2. Standardize `no_fake_completion` claim/evidence metadata.
3. Add release-gate checks for required quality gate presence.
4. Add dashboard trend views for gate-level and requirement-gap drift.
5. Sign run attestations.
