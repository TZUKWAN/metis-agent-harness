# Metis Iteration 007 - Trajectory Eval Metrics

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Move evals beyond final status and final verification.
2. Add trajectory-level metrics that expose weak small-model behavior.
3. Use metrics that can be computed from current runtime data without introducing a new trace store yet.

## Changes

1. Added `EvalResult.duplicate_tool_calls`.
2. Added `EvalResult.invalid_tool_calls`.
3. Added `EvalResult.policy_blocks`.
4. Added `EvalResult.evidence_resolution_failures`.
5. Updated eval JSON and Markdown reports to include these trajectory fields.
6. Duplicate tool calls are computed from `StateStore.tool_calls` when available, falling back to repeated tool result pairs.
7. Invalid tool calls count blocked/error calls caused by unknown tools, disallowed tools, policy denial, approval-required calls, or dangerous shell commands.
8. Policy blocks count tool results with `policy_decision` of `block`, `deny`, or `approval_required`.
9. Evidence resolution failures count finalization errors involving unresolved or missing evidence refs.
10. Added tests for duplicate tool calls, invalid calls, policy blocks, and evidence resolution failure metrics.

## Verification

```powershell
python -m pytest -q
# 141 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. TRAJECT-Bench and related trajectory-aware benchmarks emphasize that final-answer correctness misses tool selection, argument, order, and dependency failures.
2. Agent trajectory metric systems evaluate task completion, efficiency, tool selection, safety, reasoning quality, and function-call correctness over the full path.
3. Tool-spam and retry-drift discussions point to duplicate calls and repeated actions without progress as concrete production failure signals.

## Remaining P0 Gaps

1. Metrics are counted, but not yet used as pass/fail criteria in `EvalTaskSpec`.
2. Duplicate call detection uses exact serialized args; it needs canonicalization and semantic duplicate detection.
3. Invalid tool calls are inferred from error strings; ToolResult should carry structured failure categories.
4. Eval reports still lack expected trajectory matching and required tool sequence checks.
5. Retry drift is not yet measured because retry attempt metadata is not recorded.
6. Context cleanliness and constraint retention metrics are still missing.
