# Metis Iteration 003 - Safe Command Tools And Evidence Resolver

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Reduce reliance on high-risk shell execution.
2. Separate test evidence from generic command evidence.
3. Add the first resolver layer that proves evidence records point back to authoritative runtime records.
4. Keep compatibility with existing `run_shell` while creating safer defaults for future agents.

## Changes

1. Added `run_command`, a non-shell command runner that accepts either an argument list or a string parsed into arguments.
2. Added `run_test`, a non-shell test runner that returns `passed`, `test_framework`, `exit_code`, `stdout`, and `stderr`.
3. Kept `run_shell` for compatibility, but it remains policy-gated and tagged with `uses_shell=True`.
4. Extended `ToolPolicyEngine` so `run_shell`, `run_command`, and `run_test` all pass through command classification.
5. Extended `ToolDispatcher` so command/test metadata such as `exit_code`, `command`, `command_text`, `passed`, and `test_framework` is copied into `ToolResult.metadata`.
6. Extended `ToolEvidenceExtractor` so pytest/test commands are recorded as `source_type="test"` rather than generic `command`.
7. Added `EvidenceResolver`, which can resolve:
   - artifact evidence against `ArtifactStore`
   - command/test/tool evidence against `StateStore.tool_calls`
   - file evidence against the filesystem
8. Updated tests so test command evidence is now expected to be typed as `test`.

## External Reference Notes

1. OpenAI trace grading and agent eval docs emphasize evaluating the trace, not only final output.
2. LangSmith/LangChain agent eval docs emphasize trajectory-level checks for tool choice, arguments, and workflow behavior.
3. Recent agent evaluation research highlights evidence-grounding defects and mid-trajectory guardrail failures as core production risks.

## Verification

```powershell
python -m pytest -q
# 128 passed, 2 skipped

python -m compileall -q metis
# passed
```

## Remaining P0 Gaps

1. `run_command` still parses string commands for convenience; high-security profiles should require argument lists only.
2. `EvidenceResolver` is not yet wired into `FinalizationGuard` or `ClaimEvidenceMatcher`; tests cover the resolver directly, but finalization still only validates ref existence and matcher semantics.
3. Tool call rows do not yet store structured metadata separately from result JSON.
4. Approval system is still missing; policy can block or mark approval-required, but no durable approval resume flow exists.
5. Trace-level evals are still not implemented; `EvalRunner` should grade tool trajectory and evidence resolution, not only final run status.
