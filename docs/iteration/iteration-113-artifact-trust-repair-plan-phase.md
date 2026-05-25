# Iteration 113 - Artifact Trust Repair Plan Phase

This iteration adds an artifact-trust precondition phase to repair plans.

## Problem

Iteration 112 routed `attestation_untrusted` into repair tasks with `critical` priority and the `artifact-integrity-and-provenance` owner area.

The repair plan still began with ordinary release blockers. That was not precise enough. An untrusted run bundle is a precondition failure: model behavior, metric drift, and regression reasons should not be interpreted until the artifact bundle verifies.

## Changes

1. `build_repair_plan()` now detects artifact integrity tasks.
2. A task is considered artifact-integrity work when:
   - `reason == "attestation_untrusted"`;
   - or `owner_area == "artifact-integrity-and-provenance"`;
   - or it carries `trust_state`.
3. When such tasks exist, the plan starts with:
   - `phase-0-restore-artifact-trust`
4. The phase includes only artifact-integrity tasks.
5. Artifact-integrity tasks still also appear in the release-blocker phase because they are critical release blockers.
6. Existing plans without artifact-integrity tasks keep their original phase layout.

## Why This Matters

For a small-model harness, repair payload ordering is part of the architecture. A 9B model should not be asked to infer that artifact trust comes first.

The plan now states the order explicitly:

```text
restore artifact trust
-> stop release blockers
-> add targeted eval coverage
-> stabilize owner areas
```

That reduces the chance that an automated repair loop spends effort tuning prompts, tools, or runtime logic when the actual problem is a stale or corrupted run bundle.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `47 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Targeted eval stubs should emit artifact verification fixtures for `attestation_untrusted`.
2. Repair plan next actions should explicitly mention phase 0 when present.
3. Markdown reports should show attestation subject statistics.
4. Attestation signing remains future work.
