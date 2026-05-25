# Metis Iteration 005 - Strict Finalization Profile

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Add an explicit strict profile for high-reliability small-model runs.
2. Require strict `done` outputs to include evidence refs under that profile.
3. Consolidate final-output proof logic into `FinalizationGuard`.
4. Avoid keeping duplicate ref-existence checks in `AgentLoop`.

## Changes

1. Added `ModelProfile.require_done_evidence_refs`.
2. Added `small_strict` profile:
   - small context budget
   - one tool call per turn
   - strict output enabled
   - parser repair enabled
   - `status="done"` requires evidence refs
3. Updated `AgentLoop` so default `FinalizationGuard` receives `require_done_evidence_refs` from the active profile.
4. Removed the duplicate strict ref validation block from `AgentLoop`; final proof checks now flow through `FinalizationGuard`.
5. Added finalization tests proving strict done without evidence refs is blocked.
6. Added integration tests proving `small_strict` blocks empty-ref `done` and allows resolved evidence refs.

## Verification

```powershell
python -m pytest -q
# 135 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. Current harness literature treats the harness as the reliability layer around a model, with execution environment, tool integration, context management, scope negotiation, loop management, and verification as core completeness dimensions.
2. Recent harness safety audits report that task completion can be misaligned with safe execution, and that violations accumulate over longer trajectories.
3. SafeHarness-style lifecycle defenses reinforce the direction Metis is taking: context filtering, causal verification, privilege-separated tool control, and rollback/degradation around state updates.

## Remaining P0 Gaps

1. `small_strict` is available but not yet the default for real 9B eval runs.
2. `FinalizationGuard` still resolves only explicit strict refs; it should also require typed evidence for each detected claim even when the model omits refs.
3. `EvidenceResolver` needs backends for git/API/web and persisted tool-result blobs.
4. `AgentLoop` should emit structured finalization events with proof status, missing refs, unresolved refs, and claim-gate failures.
5. Eval reports should split `final` into `final_verified` and `final_unverified` or equivalent metrics.
