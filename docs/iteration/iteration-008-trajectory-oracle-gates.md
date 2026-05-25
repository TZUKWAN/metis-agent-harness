# Metis Iteration 008 - Trajectory Oracle Gates

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Turn trajectory metrics from report-only fields into eval pass/fail gates.
2. Add a deterministic first-pass trajectory oracle for required tools, forbidden tools, and required order.
3. Start moving real 9B evaluation toward workflow correctness instead of final-output plausibility.

## Changes

1. Added `EvalTaskSpec.required_tools`.
2. Added `EvalTaskSpec.forbidden_tools`.
3. Added `EvalTaskSpec.required_tool_order`.
4. Added threshold fields:
   - `max_duplicate_tool_calls`
   - `max_invalid_tool_calls`
   - `max_policy_blocks`
   - `max_evidence_resolution_failures`
5. Added `EvalResult.trajectory_failures`.
6. Eval success now fails when trajectory oracle errors are present.
7. Required tool order uses in-order subsequence matching, allowing extra tools between required steps.
8. Added tests for:
   - duplicate tool-call threshold,
   - required tools,
   - forbidden tools,
   - required tool order,
   - policy-block threshold,
   - evidence-resolution failure threshold.

## Verification

```powershell
python -m pytest -q
# 146 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. Amazon Bedrock AgentCore trajectory evaluators include in-order tool sequence matching, where expected tools must appear in order while extra tools can occur between them.
2. TRAJECT-Bench highlights tool selection, parameterization, and ordering as missing dimensions in final-answer-only evaluation.
3. Promptfoo and similar eval systems expose deterministic `trajectory:tool-sequence` style assertions for agent evaluation.

## Remaining P0 Gaps

1. Tool argument correctness is not yet evaluated.
2. Required order is name-only; it does not yet verify dependencies such as read-before-write on the same path.
3. `EvalTaskSpec` does not yet express expected tool arguments or argument predicates.
4. Real 9B eval suite still needs fixed task specs using these oracle fields.
5. Trajectory gates do not yet classify recovery quality after a failed tool/test call.
