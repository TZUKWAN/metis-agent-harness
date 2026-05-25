# Iteration 124 - Structured Requirement Criteria

This iteration upgrades requirement coverage from text-only matching to structured criteria.

## Problem

Iteration 123 made `requirements` a first-class eval task contract. The remaining problem was verification strength.

Plain string requirements can catch obvious omissions, but they cannot say which evidence source must support a requirement, which evidence ref is authoritative, or what evidence strength is acceptable.

## Changes

1. `EvalTaskSpec` now has:
   - `requirement_criteria: list[dict]`
2. `EvalRunner` passes `requirement_criteria` into quality gates.
3. Suite validation accepts `requirement_criteria` as an object list.
4. Suite schema docs and schema snapshot include `requirement_criteria`.
5. `requirements_covered` supports structured criteria with:
   - `id`
   - `text`
   - `required_source_type`
   - `required_source_ref`
   - `min_strength`
6. Gate metadata now includes:
   - `requirement_criteria`
   - `missing_requirement_ids`
7. Evidence strength is ordered:
   - `weak < medium < strong`
8. Targeted eval generation preserves `requirement_criteria` from gate metadata.

## Why This Matters

Small models should not be trusted to self-certify requirement coverage.

With structured criteria, Metis can require that a requirement is not only mentioned, but supported by the right evidence source, reference, and strength.

The verifier path is now:

```text
EvalTaskSpec.requirement_criteria
-> EvalRunner quality context
-> requirements_covered gate
-> missing_requirement_ids
-> compare / repair / targeted eval
```

## Validation

- `python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py -q`
- Result: `117 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Add `required_artifact_path` and `required_tool` support to requirement criteria.
2. Add requirement-gap trend summaries to compare reports.
3. Standardize `no_fake_completion` claim/evidence metadata.
4. Add required gate presence checks to release gates.
5. Sign run attestations.
