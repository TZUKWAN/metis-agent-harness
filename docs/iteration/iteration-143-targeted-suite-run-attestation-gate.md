# Iteration 143 - Targeted Suite Run Attestation Gate

Date: 2026-05-25

## Problem

Iteration 142 exposed CLI commands for verifying targeted eval stubs and materialized targeted suites. The next safety gap was execution.

`metis eval run-suite` could still run a materialized targeted repair suite without first verifying `targeted-eval-suite-attestation.json`.

For repair workflows, that is too weak. A materialized targeted suite is an executable regression contract. If it was tampered after generation, the harness must block before any model or deterministic fixture execution.

## Implementation

`metis eval run-suite` now detects materialized targeted suites:

- `--suite <directory>` where the directory contains `targeted-eval-suite.json`;
- `--suite <path>\targeted-eval-suite.json`.

When either form is detected, the CLI runs:

```python
verify_targeted_eval_suite_attestation(suite_dir)
```

before checking endpoint configuration or invoking the generic eval runner.

If verification fails, the command returns `1` and prints:

```text
The eval was not run because targeted suite attestation failed.
```

followed by the attestation verification failures.

Generic eval suites are unaffected.

## Harness Impact

The repair eval artifact trust chain is now enforced at execution time:

```text
targeted-eval-suite-attestation.json verifies
-> targeted-eval-suite.json trusted
-> run-suite may execute
```

This keeps 9B model calls downstream of generated contract verification.

## Tests

Focused coverage added to `tests/unit/test_cli_eval.py`:

1. `run-suite` refuses a materialized targeted suite when attestation verification fails;
2. `run-suite` verifies targeted suite attestation before running when verification passes;
3. generic suite behavior remains outside this targeted-suite gate.

## Remaining Work

1. Add a dedicated repair execution command that composes verified plan, verified stubs, verified suite, and phase enforcement.
2. Add signed attestation support.
3. Add GitHub Actions and local PowerShell examples.
