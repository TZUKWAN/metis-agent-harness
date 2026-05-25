# Iteration 042 - Task Hashes and Run Metadata

Date: 2026-05-25

## Objective

Make failure artifacts auditable across baselines by recording stable task fingerprints and run metadata.

Without stable hashes, a comparison can confuse two very different cases:

- the model or harness regressed on the same eval task;
- the eval task itself changed.

For a long-running harness project, that distinction is critical. Regression signals must be attributable to the model, harness, provider profile, or eval fixture.

## Implemented

1. Failure artifacts now include `task_spec_hashes` when task spec metadata is available:
   - `prompt_hash`
   - `constraints_hash`
   - `task_spec_hash`

2. Hashing is deterministic:
   - SHA-256
   - JSON is serialized with stable key ordering and compact separators
   - prompt hash covers only prompt text
   - constraints hash excludes task id and prompt
   - full task spec hash covers the whole task spec

3. Failure artifacts now include `run_metadata` copied from `EvalSuiteResult.metadata`.

4. Unit tests verify:
   - hashes are present
   - hash values have SHA-256 length
   - run metadata is persisted into failed task artifacts

## Design Rationale

Small-model optimization requires many eval iterations. If the eval suite shifts silently, a comparison can look like a model regression when it is actually a task definition change.

The three-hash model separates:

- prompt drift;
- constraint drift;
- full task drift.

This gives future comparison logic enough evidence to warn when baseline/current runs are not comparing the same task contract.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_runner.py tests\unit\test_failure_clusters.py
```

Result:

```text
33 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add task hash comparison into `metis eval compare`:
   - prompt changed
   - constraints changed
   - task spec changed

2. Add warning output when baseline/current task specs are not identical.

3. Add compare profile behavior:
   - release should warn but not automatically block on task hash drift
   - strict should block task hash drift
   - exploratory should record only
