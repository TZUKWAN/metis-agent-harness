# Metis Iteration 002 - Evidence And Tool Policy

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Make completion-claim detection less language-fragile.
2. Make evidence matching require successful supporting tool/evidence records.
3. Validate strict final-output refs inside `FinalizationGuard`.
4. Add the first dispatcher-level `ToolPolicyEngine`.

## Changes

1. Added English claim patterns for generated, ran, tested, uploaded, and fixed claims.
2. Changed `ClaimEvidenceMatcher` so failed tools and failed evidence cannot support completion claims.
3. Added strict-output evidence/artifact ref validation to `FinalizationGuard`.
4. Passed parsed strict output from `AgentLoop` into `FinalizationGuard`.
5. Added `ToolRiskLevel`, `ToolPolicy`, `CommandClassifier`, `ToolPolicyDecision`, and `ToolPolicyEngine`.
6. Made `ToolDispatcher` enforce policy decisions before handler execution.
7. Persisted policy decision and risk level in `ToolResult.metadata`.
8. Added tests for English false-completion detection, strict ref validation, and dangerous shell command blocking.

## External Reference Notes

1. OpenAI Agents SDK docs emphasize tracing and guardrails as first-class agent runtime concepts.
2. LangGraph docs emphasize durable execution and human-in-the-loop pause/resume as workflow infrastructure.
3. MCP authorization/security docs emphasize per-tool/per-capability scopes and runtime authorization.

## Verification

```powershell
python -m pytest -q
# 121 passed, 2 skipped

python -m compileall -q metis
# passed
```

## Remaining P0 Gaps

1. `ToolPolicyEngine` is still a first layer; it needs workspace path allowlists, network host policy, approval store, and fail-closed security hooks.
2. `EvidenceResolver` still needs real foreign-key-style validation against `ArtifactStore`, `ToolResultStore`, `StateStore`, git/API/test records.
3. Strict `status=done` does not yet force refs when no claims are present; this is intentionally left compatible for existing smoke tests but should become profile/policy configurable.
4. `run_shell` still uses `shell=True`; it is now policy-gated but still needs a safer `run_command`/`run_test` split.
5. Quality gate telemetry is still incomplete; gate events should be emitted with enough context for trace review.
