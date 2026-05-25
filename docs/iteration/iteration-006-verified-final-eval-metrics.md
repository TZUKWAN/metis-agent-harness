# Metis Iteration 006 - Verified Final Eval Metrics

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Make verified final delivery observable in runtime results.
2. Make evals distinguish `final_verified` from `final_unverified`.
3. Allow benchmark tasks to require verified final output without breaking old smoke tests.

## Changes

1. Added `FinalizationResult.verified`.
2. Added `AgentRunResult.final_verified`.
3. `FinalizationGuard` marks strict `done` outputs as verified only when they contain evidence refs and pass ref/resolution checks.
4. Added `EvalTaskSpec.require_verified_final`.
5. Added `EvalResult.final_verified` and `EvalResult.final_unverified`.
6. Updated eval JSON/Markdown report output to include final verification fields.
7. Eval success now requires verified final only when the task explicitly sets `require_verified_final=True`.
8. Added tests proving:
   - legacy smoke eval can still pass as unverified final,
   - strict verified eval passes when evidence refs resolve,
   - unverified final fails when verification is required.

## Verification

```powershell
python -m pytest -q
# 137 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. OpenAI trace grading docs emphasize grading an end-to-end trace rather than only the final answer.
2. OpenAI agent eval docs recommend trace grading for workflow-level errors.
3. Trajectory-aware evaluation research points out that final-answer-only grading misses wrong tool selection, bad parameterization, and broken execution paths.

## Remaining P0 Gaps

1. Real 9B eval tasks should set `require_verified_final=True` by default.
2. Eval reports still lack duplicate tool-call rate, retry drift, invalid invocation count, and evidence-resolution failure taxonomy.
3. `FinalizationGuard` should expose structured proof details, not just `verified=True/False`.
4. Runtime status still returns `final`; a future reporting layer should display `final_verified` distinctly without breaking API compatibility.
5. Trace-level evals should compare required tool sequence and state changes, not only final status and verification refs.
