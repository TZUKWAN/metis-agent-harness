# Iteration 127 - Portable Artifact Path Validation

Date: 2026-05-25

## Problem

Metis eval suites can now declare artifact expectations through `expected_artifacts` and `requirement_criteria.required_artifact_path`. Without path policy validation, a suite could accidentally embed:

- an absolute POSIX path;
- a Windows drive-prefixed path;
- a parent traversal path such as `../escape.md`.

That is a production harness problem. Eval suites should be portable across machines, CI runners, and scenario-specific agents. They should not depend on one developer's local checkout path, and they should not express artifact expectations that escape the intended workspace.

## Implementation

Suite validation now checks portable artifact path policy for:

- `EvalTaskSpec.expected_artifacts`
- `requirement_criteria[*].required_artifact_path`
- `requirement_criteria[*].artifact_path`

Rejected shapes:

- absolute paths beginning with `/`;
- home-relative paths beginning with `~`;
- Windows drive-prefixed paths such as `C:\tmp\report.md`;
- parent traversal segments such as `../report.md` or `outputs/../report.md`.

New validation code:

- `invalid_artifact_path`

The runtime gate still normalizes Windows/POSIX separators for observed artifact matching. The stricter suite validation applies to the declared contract, not to actual local artifact records.

## Harness Impact

This improves Metis as a reusable harness base:

1. Targeted eval suites remain portable across developer machines and CI.
2. Repair tasks cannot accidentally bake in local absolute paths.
3. Artifact contracts are constrained to the suite/workspace boundary.
4. Small models receive cleaner, more stable artifact targets.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_suite_validation.py -q
python -m compileall -q metis
```

Result:

```text
18 passed
compileall passed
```

## Remaining Work

1. Normalize or reject non-portable artifact paths when targeted eval stubs are generated from quality gate metadata.
2. Add dashboard views that group artifact path policy failures separately from model failures.
3. Add signed attestation so portable artifact paths are also tamper-evident.
4. Add real-small-model eval tasks with artifact-only criteria and portable path validation.
