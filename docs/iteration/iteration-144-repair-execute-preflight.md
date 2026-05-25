# Iteration 144 - Repair Execute Preflight

Date: 2026-05-25

## Problem

The repair flow now has several separate safety gates:

- repair-plan attestation verification;
- phase executability;
- targeted eval stubs attestation verification;
- targeted eval suite attestation verification;
- targeted suite run-time attestation gate.

Those gates are individually useful, but future repair executors need one pre-execution entry point that composes them before any model or tool repair action begins.

## Implementation

Added:

```powershell
metis eval repair-execute `
  --plan-dir <repair-plan-dir> `
  --phase <phase-id> `
  --stubs-dir <targeted-stubs-dir> `
  --suite-dir <targeted-suite-dir>
```

`--stubs-dir` and `--suite-dir` are optional.

The command is a preflight gate only. It does not edit files and does not invoke a model.

It checks:

1. repair-plan attestation verifies;
2. `repair-plan.json` exists and loads as an object;
3. requested phase is executable according to `phase_status_summary.executable_phases`;
4. targeted eval stubs attestation verifies when `--stubs-dir` is provided;
5. targeted eval suite attestation verifies when `--suite-dir` is provided.

It returns:

- `0` when every requested check passes;
- `1` when any check fails.

It supports Markdown and JSON output. JSON output includes:

- operation;
- ready flag;
- phase id;
- artifact directories;
- per-check pass/fail status;
- failure count;
- failure list.

## Harness Impact

This gives future repair execution a single deterministic readiness gate.

For 9B models, this is important because model calls must remain downstream of verified orchestration state. A repair executor should not need to remember five separate commands before it starts work; it should call one preflight gate and proceed only when `ready=true`.

## Tests

Added CLI tests for:

1. successful preflight with verified plan, stubs, and suite;
2. JSON failure when the requested phase is blocked;
3. Markdown failure when repair-plan attestation fails.

## Remaining Work

1. Implement an actual repair execution command behind this preflight.
2. Persist repair attempt status back into repair-plan tasks/phases.
3. Add signed attestation support.
4. Add GitHub Actions and local PowerShell examples.
