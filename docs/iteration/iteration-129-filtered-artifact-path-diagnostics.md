# Iteration 129 - Filtered Artifact Path Diagnostics

Date: 2026-05-25

## Problem

Iteration 128 filtered non-portable artifact paths while generating targeted eval contracts. That protected suite validity, but the filtering was too quiet. A reviewer could see that an absolute path was missing from `expected_artifacts`, but not why it was excluded.

A production harness should preserve this decision as structured diagnostic metadata. Silent filtering is risky because it makes repair generation harder to audit and makes dashboard explanations weaker.

## Implementation

Targeted eval stubs now include:

```json
"artifact_path_diagnostics": []
```

Each diagnostic entry can include:

- `task_id`
- `gate`
- `source`
- `path`
- `reason`
- `criterion_id`

Current rejection reasons:

- `not_relative`
- `windows_drive_prefix`
- `parent_traversal`

Diagnostics are collected from:

- scalar artifact metadata fields: `path`, `artifact_path`, `expected_artifact`
- list artifact metadata fields: `paths`, `artifact_paths`, `expected_artifacts`, `missing_artifact_paths`
- raw `requirement_criteria[*].required_artifact_path`
- raw `requirement_criteria[*].artifact_path`

The same diagnostics are preserved in materialized targeted suite wrapper metadata and rendered in:

- `targeted-eval-stubs.md`
- materialized suite Markdown

The diagnostics do not enter `eval_task_spec`, because filtered paths are not executable model contracts. They remain wrapper-level audit metadata.

## Harness Impact

This improves traceability:

1. The repair suite remains portable.
2. The original bad path remains explainable.
3. Dashboards can show exactly why a path was filtered.
4. Reviewers can distinguish model behavior gaps from contract-generation hygiene decisions.

This follows the broader agent-eval direction: trace and artifact decisions must be inspectable, not hidden behind a final score or a silently changed contract.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
python -m compileall -q metis
```

Result:

```text
53 passed
compileall passed
```

## Remaining Work

1. Add dashboard grouping for artifact path diagnostic reasons.
2. Add compare summary counts for filtered artifact paths by reason.
3. Add real small-model eval cases that generate artifact diagnostics from observed bad metadata.
4. Add signed artifact bundle attestation.
