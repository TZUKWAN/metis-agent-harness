# Metis Iteration 004 - Finalization Evidence Resolution

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Move `EvidenceResolver` from a standalone utility into the finalization path.
2. Prevent final answers from passing with evidence refs that exist in the ledger but do not resolve to authoritative runtime records.
3. Add integration coverage for forged or stale evidence references.

## Changes

1. `FinalizationGuard` now accepts an optional `evidence_resolver`.
2. When strict output includes `evidence_refs`, `FinalizationGuard` now resolves each referenced evidence record if a resolver is configured.
3. `AgentLoop` now constructs `FinalizationGuard` with `EvidenceResolver(state=..., artifact_store=...)` when state or artifact store is available.
4. Added unit tests proving finalization blocks existing but unresolved evidence refs.
5. Added an integration test proving `AgentLoop` blocks a final `All tests passed` claim when the referenced evidence exists in the ledger but cannot be traced to a successful tool call.

## Verification

```powershell
python -m pytest -q
# 131 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. OpenAI trace grading docs emphasize that agent quality should be assessed over end-to-end traces rather than final text alone.
2. Microsoft AgentRx describes failure diagnosis through execution trajectories and evidence-backed constraint violation logs.
3. Recent evidence-grounding research defines a key agent failure mode as treating environment-facing claims as sufficient evidence without resolving them against current authoritative state.

## Remaining P0 Gaps

1. `ClaimEvidenceMatcher` still does not receive resolver output directly; finalization resolves strict refs, but generic claim matching still uses typed heuristics.
2. `FinalizationGuard` does not yet require non-empty refs for every `status=done`; existing compatibility remains, but a stricter profile should mandate refs for completion claims.
3. `EvidenceResolver` needs richer backends for git/API/web/test reports and tool-result blobs persisted outside SQLite.
4. `AgentLoop` still has duplicate strict ref existence checks before finalization; this should be consolidated so all final-output proof logic lives in one place.
5. Trace-level evals still need to score whether evidence resolution occurred, not just whether the final status was `final`.
