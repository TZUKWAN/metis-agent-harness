# Iteration 146 - Repair Execute Preflight Attestation

Date: 2026-05-25

## Problem

Iteration 145 made repair-execute readiness durable by writing:

- `repair-execute-preflight.json`
- `repair-execute-preflight.md`

That created a new control-plane artifact. If the preflight decision can be edited after generation, a later CI step or repair executor could trust a stale or tampered readiness decision.

## Implementation

`metis eval repair-execute --output-dir <directory>` now also writes:

- `repair-execute-preflight-attestation.json`
- `repair-execute-preflight-attestation.md`

The attestation uses the existing repair eval artifact predicate:

```text
https://metis.local/attestations/repair-eval-artifacts/v1
```

with artifact type:

```text
repair-execute-preflight
```

Added standalone verification:

```powershell
metis eval verify-repair-preflight --preflight-dir <directory>
```

The command supports `--json`, returns `0` when verification passes, and returns `1` when verification fails.

## Harness Impact

The repair execution approval decision is now tamper-evident.

The trust chain now covers:

```text
repair plan
-> targeted eval stubs
-> targeted eval suite
-> repair-execute preflight decision
```

Future repair executors can require a verified preflight artifact before invoking a model or tool.

## Tests

Focused CLI and docs tests cover:

1. `repair-execute --output-dir` writes preflight attestation files;
2. `verify-repair-preflight` passes with no failures;
3. `verify-repair-preflight --json` returns non-zero with failure details;
4. CI recipe mentions preflight attestation artifacts and verification command.

## Remaining Work

1. Add a dedicated repair execution command behind this verified preflight.
2. Persist repair attempt status back into repair-plan tasks and phases.
3. Add signed attestation support.
