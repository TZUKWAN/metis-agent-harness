# Metis Iteration 011 - Pre-Execution Schema Guard

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Move tool argument schema validation from eval-only to pre-execution enforcement.
2. Prevent schema-invalid tool calls from reaching handlers and causing side effects.
3. Keep invalid calls visible to AgentLoop and EvalRunner so small models can recover and evals can score the failure.

## Changes

1. `ToolDispatcher` now owns a `ToolArgumentSchemaValidator`.
2. Dispatcher validates `ToolCall.arguments` against `ToolSpec.parameters` after policy/guardrails and before `tool.pre_dispatch` hooks or handler execution.
3. Schema-invalid calls return `ToolResult(status="blocked")`.
4. Schema-invalid calls include:
   - `metadata["schema_valid"] = False`
   - `metadata["schema_errors"] = [...]`
   - existing policy decision/risk metadata
5. Successful calls include `metadata["schema_valid"] = True`.
6. EvalRunner now consumes dispatcher-level schema errors first, instead of recomputing them when already present.
7. Invalid tool-call counting now treats schema validation failures as invalid tool calls.
8. Added dispatcher and AgentLoop tests proving schema-invalid calls do not execute handlers.

## Verification

```powershell
python -m pytest -q
# 157 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. OpenAI Agents SDK tool guardrails describe validating or blocking tool calls before and after execution.
2. Production pre-execution validation systems emphasize checking actions before tool execution, independent of model/provider.
3. ToolSafe and TraceSafe-style research emphasizes real-time, step-level tool-call intervention before unsafe execution.

## Remaining P0 Gaps

1. Schema-invalid tool calls are blocked but not yet fed into a dedicated repair loop.
2. `ToolDispatcher` still treats schema failure as `blocked`; a richer status/failure category would separate schema_invalid from policy_blocked.
3. `ToolArgumentSchemaValidator` still needs support for `additionalProperties`, numeric ranges, string patterns, length, and array min/max.
4. Schema validation does not yet check argument provenance or role-specific argument policies.
5. Tool output schema validation is still missing.
