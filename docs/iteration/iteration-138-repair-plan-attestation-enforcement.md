# Iteration 138 - Repair Plan Attestation Enforcement

Date: 2026-05-25

## Problem

Iteration 137 made repair plans tamper-evident by writing repair-plan attestations.

The next gap was enforcement. A command could require a phase to be executable, but still make that decision from an unattested or unverified plan artifact.

For the harness control plane, phase executability and artifact trust must be checked together:

1. generate the repair plan;
2. write the repair plan artifacts;
3. verify the repair-plan attestation;
4. only then enforce requested phase executability.

## Implementation

`metis eval repair-plan --require-executable-phase <phase-id>` now requires `--output-dir`.

This is intentional. A phase enforcement decision is only release-grade when the plan is written as artifacts and those artifacts are attested.

When phase enforcement is requested, the CLI now:

1. builds the repair plan;
2. writes `repair-plan.json`, `repair-plan.md`, and attestation files to `--output-dir`;
3. runs `verify_repair_plan_attestation(output_dir)`;
4. fails before phase enforcement if attestation verification fails;
5. checks requested phase ids only after attestation passes.

Failure modes:

- missing `--output-dir`:

```text
Repair phase enforcement requires --output-dir so repair-plan attestation can be written and verified.
```

- attestation failure:

```text
Repair plan attestation failed: <verification failure>
```

- blocked phase:

```text
Required repair phase is not executable: <phase-id> status=<status> blocked_by=<phase-list>
```

## Harness Impact

This connects repair-plan integrity to repair-plan execution safety.

Before this iteration, phase enforcement checked plan status metadata. After this iteration, it also requires the plan artifact to verify before that metadata is trusted.

For 9B model orchestration, this is important because the model should never be asked to act on unaudited control-plane state. The harness now blocks two unsafe conditions before model work:

1. the requested phase is blocked by hard preconditions;
2. the repair-plan artifact cannot verify.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_cli_eval.py -q
```

Result:

```text
42 passed
```

New coverage verifies:

1. phase enforcement without `--output-dir` fails;
2. failed repair-plan attestation blocks phase enforcement;
3. blocked executable phase still fails with status and blocked-by diagnostics;
4. executable phase passes when attestation verification passes.

## Remaining Work

1. Add a dedicated `metis eval verify-repair-plan` command.
2. Add repair-plan attestation verification to future repair execution commands.
3. Add signed attestation support.
4. Add attestation for targeted eval stubs and materialized suites.
