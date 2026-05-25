# Iteration 045 - Environment Drift Compare

Date: 2026-05-25

## Objective

Make eval run comparison detect provider/model/runtime environment drift.

Task hash drift explains whether the eval changed. Environment drift explains whether the execution context changed. Both are required to interpret baseline comparisons correctly.

## Implemented

1. Run summaries now expose:
   - suite
   - model
   - base URL
   - runtime profile
   - task count

2. Comparison output now includes `environment_diff`:
   - `suite_changed`
   - `model_changed`
   - `base_url_changed`
   - `profile_changed`
   - `task_count_changed`

3. Markdown output now includes:
   - `## Environment Drift`

4. Profile behavior:
   - `release`: reports environment drift but does not block on it
   - `strict`: blocks environment drift
   - `exploratory`: records drift without blocking

## Design Rationale

Baseline comparison is only meaningful when execution context is visible.

A model change, endpoint change, runtime profile change, or task count change can explain a result shift. The comparison should not hide that context inside raw manifests. It should surface it as a first-class section in JSON and Markdown.

Strict mode blocks environment drift because it is intended for controlled harness hardening. Release mode reports it but does not block because model upgrades may be intentional release candidates.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
15 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Regression reason linking:
   - map each reason to task ids
   - map each reason to cluster keys
   - map each reason to failure artifact paths

2. Failure diagnosis report:
   - combine task contract
   - tool excerpt
   - cluster
   - remediation backlog action

3. Trace timeline export:
   - model calls
   - tool calls
   - blocked calls
   - evidence checks
   - finalization checks
