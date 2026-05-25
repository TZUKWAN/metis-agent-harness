# Iteration 044 - Task Spec Drift Compare

Date: 2026-05-25

## Objective

Make eval run comparison detect whether the eval task contract changed between baseline and current runs.

This closes an important attribution gap. If a prompt, required tool, forbidden tool, evidence requirement, or threshold changed, the comparison must surface that fact separately from model/harness behavior.

## Implemented

1. `EvalSuiteResult.write_reports()` now writes `task-specs.json`.

2. `task-specs.json` contains every task from `EvalRunner.run_suite()`:
   - task id
   - full task spec
   - prompt hash
   - constraints hash
   - full task spec hash

3. `compare_eval_runs()` now reads task spec hashes from:
   - `task-specs.json`
   - fallback failed-task artifacts for older partial runs

4. Comparison output now includes `task_spec_diff`:
   - `baseline_task_specs`
   - `current_task_specs`
   - `prompt_changed`
   - `constraints_changed`
   - `task_spec_changed`
   - `missing_baseline_specs`
   - `missing_current_specs`

5. Markdown output now includes `## Task Spec Drift`.

6. Profile behavior:
   - `release`: reports task spec drift but does not block on it
   - `strict`: blocks task spec drift and missing task spec data
   - `exploratory`: records drift without blocking

## Design Rationale

Baseline comparison only works when compared tasks mean the same thing.

For small-model harness development, evals will evolve frequently: prompts get clearer, schema repair expectations change, evidence requirements become stricter, and tool constraints expand. Those changes are useful, but they must be visible. Otherwise a stricter eval can look like a model regression, or an easier eval can hide a harness regression.

Task spec drift reporting gives future release automation enough context to say:

- the model regressed on the same task;
- the task changed and the comparison needs review;
- both the task and behavior changed.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_eval_runner.py
```

Result:

```text
43 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Link regression reasons to concrete artifacts:
   - task ids
   - failure artifact paths
   - cluster keys
   - task spec drift records

2. Generate a `failure-diagnosis.md` report.

3. Add provider/model drift comparison:
   - model changed
   - base URL changed
   - runtime profile changed
   - suite task count changed
