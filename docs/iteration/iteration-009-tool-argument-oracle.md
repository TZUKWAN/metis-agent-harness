# Metis Iteration 009 - Tool Argument Oracle

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Close the gap where a model calls the right tool with the wrong arguments.
2. Add deterministic argument checks to trajectory evals.
3. Support lightweight predicates suitable for real fixture tasks.

## Changes

1. Added `EvalTaskSpec.required_tool_arguments`.
2. The field accepts a list of expected tool-call specs:

```json
{
  "tool": "run_test",
  "arguments": {
    "command": {"contains": "pytest"}
  }
}
```

3. Argument matching supports:
   - exact primitive equality,
   - partial nested dict matching,
   - exact list matching,
   - predicate objects: `equals`, `contains`, `startswith`, `endswith`, `in`.
4. Eval trajectory errors now include `Required tool arguments not satisfied` when no actual tool call matches the expected tool and argument predicates.
5. Added tests for:
   - matching `run_test.command contains pytest`,
   - failing `run_test.command contains pytest` when the model used unittest,
   - exact `write_file.path == report.md`.

## Verification

```powershell
python -m pytest -q
# 149 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. TRAJECT-Bench reports tool selection, argument correctness, and order/dependency satisfaction as trajectory-level diagnostics.
2. Ragas `ToolCallAccuracy` and MLflow `ToolCallCorrectness` both treat correct arguments as part of agent/tool-call evaluation, not just tool name selection.
3. Production tool-calling discussions repeatedly identify argument validation as the under-instrumented handoff between model output and real side effects.

## Remaining P0 Gaps

1. Argument predicates are deterministic but basic; they do not yet support regex, numeric ranges, path normalization, or schema-aware type validation.
2. Tool argument matching does not yet validate against `ToolSpec.parameters` JSON Schema.
3. There is no per-call score; the oracle is pass/fail at task level.
4. Required tool arguments do not yet bind to a specific occurrence when the same tool is called multiple times.
5. Real 9B eval specs still need to be rewritten to use required tool arguments, strict final verification, and trajectory thresholds.
