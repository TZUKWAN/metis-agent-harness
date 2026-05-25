# Repair Plan CI Recipe

This recipe defines the standard CI sequence for turning an eval regression into a verified repair plan and a safely executable repair phase.

The purpose is not to ask a model what to do next. The purpose is to make the harness prove that the control-plane artifacts are valid before any model repair work begins.

## Inputs

Required inputs:

- baseline eval run directory;
- current eval run directory;
- release profile, usually `release` or `strict`;
- output directories for comparison, repair tasks, and repair plan.

Example variables:

```powershell
$baseline = "docs/evals/runs/baseline"
$current = "docs/evals/runs/current"
$comparison = "docs/evals/runs/current/comparison"
$repair = "docs/evals/runs/current/repair"
$plan = "docs/evals/runs/current/repair-plan"
```

## Step 1 - Compare Runs

```powershell
metis eval compare `
  --baseline $baseline `
  --current $current `
  --profile release `
  --output-dir $comparison
```

This produces:

- `comparison.json`
- `comparison.md`
- diagnosis-ready regression reasons and reason links

CI should stop here if comparison returns non-zero and the policy is "do not auto-plan failed releases." If the policy is "always generate repair artifacts," continue to the next step while preserving the failed exit code as the release decision.

## Step 2 - Diagnose Repair Tasks

```powershell
metis eval diagnose `
  --comparison $comparison `
  --output-dir $repair
```

This produces:

- `repair-tasks.json`
- `repair-tasks.md`

Repair tasks preserve:

- regression reasons;
- owner areas;
- recommended actions;
- source module hints;
- suggested evals;
- trust state when attestation failed;
- artifact path diagnostics when suite hygiene failed.

## Step 3 - Build Repair Plan

```powershell
metis eval repair-plan `
  --repair-tasks $repair `
  --output-dir $plan
```

This produces:

- `repair-plan.json`
- `repair-plan.md`
- `repair-plan-attestation.json`
- `repair-plan-attestation.md`

Optional hardened signing:

- Set `METIS_ATTESTATION_SIGNING_KEY` before generating attestations to add an HMAC signature to run, repair-plan, targeted-eval-stub, targeted-suite, and repair-execute-preflight attestation JSON.
- Set `METIS_ATTESTATION_KEY_ID` when CI needs a stable key label instead of the default derived key id.
- Set `METIS_REQUIRE_ATTESTATION_SIGNATURE=1` in hardened CI when unsigned attestations must fail verification instead of being accepted as digest-only local attestations.

The plan includes:

- priority buckets;
- owner areas;
- phase ordering;
- hard preconditions;
- phase status;
- blocked-by chains;
- executable phase list.

## Step 4 - Verify Repair Plan Attestation

```powershell
metis eval verify-repair-plan `
  --plan-dir $plan
```

Machine-readable form:

```powershell
metis eval verify-repair-plan `
  --plan-dir $plan `
  --json
```

CI must treat non-zero exit as a hard failure. A repair plan whose attestation does not verify must not drive model repair, phase enforcement, dashboard status, or release decisions.

## Step 5 - Require An Executable Phase

Before running model or infrastructure repair work for a phase, require that phase to be executable:

```powershell
metis eval repair-plan `
  --repair-tasks $repair `
  --output-dir $plan `
  --require-executable-phase phase-1-stop-release-blockers
```

This command verifies repair-plan attestation before checking phase status.

It fails when:

- `--output-dir` is missing;
- repair-plan attestation fails;
- the requested phase is absent;
- the requested phase is blocked by an incomplete hard precondition;
- the requested phase is otherwise not executable.

## Step 6 - Verify Repair Eval Artifacts

When targeted eval stubs are generated, verify their attestation before materializing or reviewing them:

```powershell
metis eval eval-stubs `
  --repair-tasks $repair `
  --output-dir "$current/targeted-stubs"

metis eval verify-eval-stubs `
  --stubs-dir "$current/targeted-stubs"
```

Expected attestation artifacts:

- `targeted-eval-stubs-attestation.json`
- `targeted-eval-stubs-attestation.md`

When targeted eval suites are materialized, verify their attestation before running them:

```powershell
metis eval materialize-stubs `
  --stubs "$current/targeted-stubs" `
  --output-dir "$current/targeted-suite"

metis eval verify-targeted-suite `
  --suite-dir "$current/targeted-suite"
```

Expected attestation artifacts:

- `targeted-eval-suite-attestation.json`
- `targeted-eval-suite-attestation.md`

CI must treat either verification failure as a hard failure. Generated repair eval contracts are executable inputs to later model work and must be tamper-evident.

## Step 7 - Preflight Repair Execution

Before connecting a model or infrastructure repair executor, run a single preflight that composes the verified artifacts and phase gate:

```powershell
metis eval repair-execute `
  --plan-dir $plan `
  --phase phase-1-stop-release-blockers `
  --stubs-dir "$current/targeted-stubs" `
  --suite-dir "$current/targeted-suite" `
  --output-dir "$current/repair-execute-preflight"
```

Machine-readable form:

```powershell
metis eval repair-execute `
  --plan-dir $plan `
  --phase phase-1-stop-release-blockers `
  --stubs-dir "$current/targeted-stubs" `
  --suite-dir "$current/targeted-suite" `
  --output-dir "$current/repair-execute-preflight" `
  --json
```

To persist an auditable execution attempt and updated repair-plan snapshot, add attempt recording:

```powershell
metis eval repair-execute `
  --plan-dir $plan `
  --phase phase-1-stop-release-blockers `
  --stubs-dir "$current/targeted-stubs" `
  --suite-dir "$current/targeted-suite" `
  --output-dir "$current/repair-execute-preflight" `
  --record-attempt-status in_progress `
  --executor-id "ci-repair-executor"
```

Attempt recording writes:

- `repair-execute-attempt/repair-execute-attempt.json`
- `repair-execute-attempt/repair-execute-attempt.md`
- `updated-repair-plan/repair-plan.json`
- `updated-repair-plan/repair-plan.md`
- `updated-repair-plan/repair-plan-attestation.json`
- `updated-repair-plan/repair-plan-attestation.md`

If preflight is not ready, the persisted attempt status is forced to `blocked`.

This command is a pre-execution safety gate. It does not edit code and does not invoke a model. It returns `0` only when:

- repair-plan attestation verifies;
- `repair-plan.json` can be loaded;
- the requested phase is executable;
- targeted eval stubs attestation verifies when `--stubs-dir` is provided;
- targeted eval suite attestation verifies when `--suite-dir` is provided.

Future repair executors should call this gate before model or tool execution.

Expected preflight artifacts:

- `repair-execute-preflight.json`
- `repair-execute-preflight.md`
- `repair-execute-preflight-attestation.json`
- `repair-execute-preflight-attestation.md`

Verify the preflight artifact before using it as an execution approval:

```powershell
metis eval verify-repair-preflight `
  --preflight-dir "$current/repair-execute-preflight"
```

## Precondition Phases

Known hard precondition phases:

- `phase-0-restore-artifact-trust`
- `phase-0b-repair-suite-hygiene`

These phases must complete before behavior repair is trusted.

Artifact trust failures mean the run bundle is unauditable.

Suite hygiene failures mean eval contracts or quality gate metadata contain invalid artifact paths or related dirty contract metadata.

## CI Policy

Recommended CI policy:

1. run compare;
2. always write comparison artifacts;
3. diagnose repair tasks for failed release/strict comparisons;
4. write and attest repair plan;
5. verify repair-plan attestation;
6. verify targeted eval stubs before materializing them;
7. verify materialized targeted eval suites before running them;
8. run `repair-execute` preflight before model or tool repair;
9. verify `repair-execute` preflight attestation;
10. require only the phase CI intends to execute;
11. never invoke a model on a blocked phase;
12. never invoke a model from an unattested repair plan;
13. never invoke a model from an unattested preflight decision;
14. archive comparison, repair tasks, repair plan, targeted eval artifacts, preflight artifacts, and attestation artifacts.

## Why This Matters For 9B Models

Small models should not make orchestration trust decisions.

The harness must decide:

- whether eval run artifacts are trustworthy;
- whether suite contracts are clean;
- whether repair-plan artifacts are tamper-evident;
- whether generated repair eval artifacts are tamper-evident;
- whether a phase is executable;
- whether model behavior repair is allowed to proceed.

This recipe keeps 9B model calls downstream of deterministic checks.
