# Iteration 116 - Fixture Quality Gate Results

This iteration persists quality gate results for deterministic artifact fixtures.

## Problem

Iteration 115 made `artifact_verification` fixtures executable without provider calls. The fixture could pass or fail, but the structured gate result was not part of `EvalResult`.

That left dashboards and repair agents with weak evidence: they could see `quality_failures` and `errors`, but not the gate name, pass/fail state, message, or metadata.

## Changes

1. `EvalResult` now includes:
   - `quality_gate_results`
2. Each gate result records:
   - `name`
   - `passed`
   - `message`
   - `metadata`
3. Artifact verification fixtures now run through `QualityGateRunner`.
4. Default deterministic gate:
   - `run_attestation_verifies`
5. Successful fixture results include target run metadata.
6. Failed fixture results keep the gate message in both:
   - `quality_gate_results`
   - `errors`
7. `eval-report.json` includes the new field automatically.
8. `eval-report.md` now has:
   - `## Quality Gate Results`

## Why This Matters

Small-model repair loops need structured evidence. A 9B model should not parse prose to determine which verifier failed.

The result now carries a direct machine-readable chain:

```text
artifact_verification fixture
-> run_attestation_verifies gate
-> pass/fail message
-> target_run_dirs metadata
```

This improves CI integration, dashboards, and downstream repair task generation.

## Validation

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_quality_gates.py -q`
- Result: `61 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Model behavior eval quality gates should also persist gate result metadata.
2. Failure artifacts and timelines should include quality gate result details.
3. Comparison can later detect gate result drift.
4. Attestation signing remains future work.
