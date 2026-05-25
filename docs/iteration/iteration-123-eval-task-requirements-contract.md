# Iteration 123 - Eval Task Requirements Contract

This iteration adds `requirements` as a first-class `EvalTaskSpec` field.

## Problem

Iteration 122 surfaced `missing_requirements` in targeted eval prompts and materialized suite wrappers. That made requirement gaps visible to the model and to downstream tooling.

The runtime gate still needed a structured contract. `requirements_covered` reads `context["requirements"]`, but `EvalRunner` did not pass task-level requirements into the quality gate context.

## Changes

1. `EvalTaskSpec` now has:
   - `requirements: list[str]`
2. `EvalRunner._quality_gate_results()` passes `task.requirements` to the quality gate context.
3. Suite validation treats `requirements` as a string-list field.
4. The machine-readable suite schema snapshot includes `requirements`.
5. The suite schema documentation describes `requirements` as acceptance criteria that quality gates can verify.
6. Targeted eval generation now derives `requirements` from quality gate metadata:
   - `requirements`
   - `requirement`
   - `missing_requirements`
   - `missing_requirement`
7. `requirements_covered` drift now becomes an executable runtime contract, not only prompt text.

## Why This Matters

Small models perform better when the harness owns the contract.

With this change, requirement coverage has a closed loop:

```text
requirements_covered fails
-> missing_requirements metadata
-> repair task
-> targeted eval task_spec.requirements
-> runtime requirements_covered gate
```

The model can still produce the repair, but the harness validates whether the acceptance criteria were actually covered.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`
- Result: `111 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. `requirements_covered` should evolve beyond substring matching into requirement ids, evidence refs, and source tiers.
2. `no_fake_completion` should emit standardized claim/evidence metadata.
3. Release gates should support required gate presence checks.
4. Dashboards should show requirement-gap trends.
5. Run attestations should be signed.
