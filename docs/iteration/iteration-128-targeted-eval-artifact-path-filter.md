# Iteration 128 - Targeted Eval Artifact Path Filter

Date: 2026-05-25

## Problem

Iteration 127 made suite validation reject non-portable artifact paths. That exposed the next link in the chain: targeted eval generation could still compile artifact paths directly from quality gate metadata.

Quality gate metadata often comes from observed runtime state. It may contain:

- absolute local paths;
- Windows drive-prefixed paths;
- parent traversal paths;
- paths copied from a developer workstation rather than a portable suite contract.

If those values are copied directly into `eval_task_spec.expected_artifacts` or `requirement_criteria.required_artifact_path`, the generated repair suite can fail validation before it even evaluates model behavior.

## Implementation

`metis.evals.compare` now filters artifact paths before compiling quality gate metadata into executable targeted eval contracts.

Filtered fields:

- `expected_artifacts`
- artifact gate metadata fields:
  - `path`
  - `artifact_path`
  - `expected_artifact`
  - `paths`
  - `artifact_paths`
  - `expected_artifacts`
- `missing_artifact_paths`
- `requirement_criteria[*].required_artifact_path`
- `requirement_criteria[*].artifact_path`

Rejected shapes:

- empty paths;
- absolute POSIX paths;
- home-relative paths beginning with `~`;
- Windows drive-prefixed paths;
- parent traversal segments.

For raw `requirement_criteria`, non-portable artifact fields are removed before the criterion is added to a generated eval. If the criterion has no remaining verifier field after removal, it is skipped.

## Harness Impact

This strengthens the repair loop:

1. Runtime metadata remains available for diagnosis.
2. Generated targeted eval contracts stay portable.
3. Suite validation and suite generation now agree on artifact path policy.
4. A failed run on one machine can produce a repair suite that can be validated and reused elsewhere.

For 9B/flash models, this keeps the generated repair task clean. The model sees stable relative artifact targets instead of local filesystem noise.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py tests\unit\test_eval_suite_validation.py -q
python -m compileall -q metis
```

Result:

```text
71 passed
compileall passed
```

## Remaining Work

1. Add explicit diagnostic metadata for filtered non-portable artifact paths so dashboards can explain why a path was excluded from the executable contract.
2. Group artifact path policy failures separately in compare and dashboard views.
3. Expand real small-model suites with artifact-only criteria using portable paths.
4. Add signed run attestation for portable artifact bundles.
