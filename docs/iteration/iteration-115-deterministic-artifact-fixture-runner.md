# Iteration 115 - Deterministic Artifact Fixture Runner

This iteration makes artifact verification fixtures executable.

## Problem

Iteration 114 generated `artifact_verification` stubs for `attestation_untrusted` repair tasks. Those stubs correctly stated `requires_model_execution=false`, but the runner still treated eval suites as provider-driven work.

That meant a deterministic artifact fixture could still be blocked by missing model endpoint environment variables, even though no model call was needed.

## Changes

1. `EvalTaskSpec` now supports:
   - `fixture_type`
   - `requires_model_execution`
   - `artifact_verification`
2. Suite payload loading enriches artifact fixtures:
   - reads top-level `baseline.run_dir` and `current.run_dir`;
   - maps `artifact_verification.target_runs` to `artifact_verification.target_run_dirs`.
3. `EvalRunner.run_task()` now bypasses `AgentLoop` when:
   - `requires_model_execution == False`
4. `fixture_type=artifact_verification` runs:
   - `verify_run_attestation()` for every target run directory.
5. Successful fixture result:
   - `status=verified`
   - `turns_used=0`
   - `tool_calls=0`
6. Failed fixture result:
   - `status=failed`
   - `quality_failures` equals attestation failure count;
   - errors include side-specific attestation failures.
7. Added quality gate:
   - `run_attestation_verifies`
8. Added:
   - `generic_eval_suite_requires_model_execution(suite_path)`
9. CLI behavior:
   - suites with model tasks still require provider env vars;
   - all-deterministic fixture suites can run without provider env vars;
   - no fake model result is produced.
10. Suite schema docs and JSON snapshot now define:
    - `fixture_type`
    - `requires_model_execution`
    - `artifact_verification`

## Why This Matters

Metis is a harness, not merely an eval caller. Some checks must be deterministic infrastructure checks. Artifact attestation verification is one of them.

The execution split is now explicit:

```text
requires_model_execution=true
-> provider-backed model behavior eval

requires_model_execution=false + fixture_type=artifact_verification
-> local deterministic attestation verifier
```

This reduces token spend, prevents fake model work, and gives small models cleaner repair inputs.

## Validation

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_cli_eval.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_quality_gates.py -q`
- Result: `118 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Deterministic fixture reports should have clearer Markdown status labels.
2. Quality gate result metadata should be persisted for deterministic fixture runs.
3. Suite schema validation can constrain `artifact_verification.target_runs` to `baseline/current`.
4. Attestation signing remains future work.
