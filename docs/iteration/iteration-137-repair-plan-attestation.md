# Iteration 137 - Repair Plan Attestation

Date: 2026-05-25

## Problem

Iterations 133-136 turned repair plans into execution-control artifacts:

- precondition phases;
- hard-precondition metadata;
- phase status;
- CLI enforcement.

That made the repair plan more important. It is no longer just a human-readable checklist. It can decide whether model behavior repair is allowed to run.

If `repair-plan.json` or `repair-plan.md` can be changed after generation without detection, then CI, dashboards, and future repair executors may trust stale or tampered execution-control metadata.

For a harness intended to compensate for weak 9B models, orchestration artifacts need the same integrity treatment as eval run artifacts.

## Implementation

Added repair-plan attestation helpers in `metis.evals.attestation`:

- `build_repair_plan_attestation()`
- `write_repair_plan_attestation()`
- `verify_repair_plan_attestation()`
- `repair_plan_attestation_to_markdown()`

The new attestation uses the same in-toto statement shape as run attestation, but with a dedicated predicate type:

```text
https://metis.local/attestations/repair-plan/v1
```

`write_repair_plan()` now writes:

- `repair-plan.json`
- `repair-plan.md`
- `repair-plan-attestation.json`
- `repair-plan-attestation.md`

The repair-plan attestation subjects are:

- `repair-plan.json`
- `repair-plan.md`

The attestation files are excluded from their own subject list to avoid recursive self-reference.

The predicate records:

- builder id;
- output directory;
- profile;
- task count;
- phase count;
- hard precondition phase ids;
- generated timestamp;
- artifact count.

Verification checks:

1. attestation JSON exists;
2. statement type is correct;
3. predicate type is the repair-plan predicate;
4. subject list is present;
5. no self-subjects are included;
6. subject files exist;
7. SHA256 digests match current bytes;
8. sizes match;
9. required subjects `repair-plan.json` and `repair-plan.md` are present.

## Harness Impact

Repair plans are now tamper-evident local artifacts.

This closes a trust gap in the repair loop:

```text
comparison -> diagnosis -> repair tasks -> repair plan -> phase enforcement
```

The plan now carries an integrity envelope before it is consumed by CI or future repair executors. If a plan is modified after generation, verification can detect it before model execution or release gating proceeds.

This is harness-level infrastructure. It does not depend on any specific agent scenario, and every future scenario-specific agent benefits from trustworthy repair orchestration.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py tests\unit\test_run_attestation.py -q
```

Result:

```text
60 passed
```

New coverage verifies:

1. `plan_repairs(..., output_dir=...)` writes repair-plan attestation files;
2. `write_repair_plan()` writes JSON, Markdown, and attestation artifacts;
3. attestation subject list includes only `repair-plan.json` and `repair-plan.md`;
4. verification passes immediately after writing;
5. verification detects digest drift after `repair-plan.md` is tampered.

## Remaining Work

1. Add CLI command to verify repair-plan attestation directly.
2. Add repair-plan attestation verification to phase enforcement.
3. Add signed attestation support using external signing or Sigstore-compatible flow.
4. Add attestation for targeted eval stubs and materialized suites.
