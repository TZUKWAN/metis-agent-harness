# Iteration 136 - Repair Plan CLI Phase Enforcement

Date: 2026-05-25

## Problem

Iteration 135 added phase status and blocked-by metadata to repair plans. The next gap was CLI enforcement.

Without a command-line enforcement hook, automation could still generate a plan and then proceed to run a blocked phase by mistake. For a 9B-oriented harness, this is the wrong failure mode. The deterministic control plane should reject unsafe repair execution before the model is asked to act.

## Implementation

`metis eval repair-plan` now supports:

```powershell
--require-executable-phase <phase-id>
```

The flag can be repeated.

After generating and optionally writing the repair plan, the CLI checks each requested phase against:

```json
phase_status_summary.executable_phases
```

The command returns non-zero when a required phase is:

1. absent;
2. blocked by an incomplete hard precondition;
3. not executable for any other status reason.

Failure messages are written to stderr and include:

- phase id;
- current status;
- blocked-by preconditions.

Example failure:

```text
Required repair phase is not executable: phase-1-stop-release-blockers status=blocked blocked_by=phase-0b-repair-suite-hygiene
```

The command still prints or writes the plan before returning non-zero, so CI logs retain the diagnostic artifact that explains the failure.

## Harness Impact

This is the first enforcement layer built on the new phase status model.

The repair loop now has a deterministic guardrail:

1. generate repair tasks;
2. build repair plan;
3. require the phase intended for execution;
4. fail fast if hard preconditions are still open.

This keeps small models from being invoked on contaminated repair surfaces. Artifact trust and suite hygiene must be resolved before behavior repair automation proceeds.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q
```

Result:

```text
97 passed
```

New coverage verifies:

1. a blocked required phase returns exit code 1;
2. the error message includes status and blocked-by phase id;
3. an executable required phase returns exit code 0;
4. existing repair-plan JSON/Markdown behavior remains intact.

## Remaining Work

1. Add a dedicated repair execution command that consumes the same phase enforcement.
2. Persist phase status changes after each repair attempt.
3. Add dashboard rendering for blocked phase chains.
4. Add attestation over repair-plan JSON and Markdown outputs.
