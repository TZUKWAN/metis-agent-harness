# Iteration 114 - Artifact Verification Stubs

This iteration prevents artifact trust failures from becoming ordinary model-behavior evals.

## Problem

Iteration 113 made artifact integrity repair a phase-0 precondition in repair plans. The next step was targeted eval generation.

Before this iteration, every repair task became the same kind of targeted eval stub. That was wrong for `attestation_untrusted`: a digest mismatch or missing attestation is not model behavior. Asking a small model to reproduce that as a behavioral eval would blur the repair boundary.

## Changes

1. `_eval_stub_for_repair_task()` now branches on artifact integrity tasks.
2. Artifact integrity tasks produce:
   - `stub_type: artifact_verification`
   - `id: artifact-verification-<repair-id>`
   - preserved `trust_state`
   - side-specific `target_runs`
3. The generated `eval_task_spec` includes:
   - `fixture_type: artifact_verification`
   - `requires_model_execution: False`
   - `allowed_tools: []`
   - `max_turns: 1`
   - `quality_gates: ["run_attestation_verifies"]`
   - `artifact_verification.required_checks`
4. Markdown renders:
   - stub type;
   - target runs;
   - trust state.
5. Materialized targeted suites preserve:
   - `stub_type`
   - `trust_state`
   - `target_runs`

## Why This Matters

Metis should make small models stronger by removing ambiguity. An artifact integrity failure should produce an artifact verification fixture, not a model prompt.

The new path is:

```text
attestation_untrusted repair task
-> artifact_verification stub
-> deterministic run attestation verifier
```

This keeps provider calls focused on actual model behavior while deterministic harness checks handle artifact integrity.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `48 passed`

## Remaining Gaps

1. Generic suite runner should execute `requires_model_execution=False` fixtures through deterministic verifiers.
2. Suite schema docs should define artifact verification fixture fields.
3. `run_attestation_verifies` should be added to quality gate inventory.
4. Signed attestations remain future work.
