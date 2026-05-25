# Metis Iteration 010 - Tool Schema Validation

Date: 2026-05-25

Status: completed for this slice. The long-running goal remains active.

## Focus

1. Detect bad tool arguments even when the tool name is correct.
2. Validate actual tool calls against `ToolSpec.parameters`.
3. Add a schema-violation metric and pass/fail threshold for eval tasks.

## Changes

1. Added `metis.tools.schema_validator.ToolArgumentSchemaValidator`.
2. The validator supports the JSON-schema subset currently used by Metis tools:
   - `type`
   - `required`
   - `properties`
   - `items`
   - `enum`
   - `oneOf`
3. Added `SchemaValidationResult`.
4. Added `EvalResult.schema_violations`.
5. Added `EvalTaskSpec.max_schema_violations`.
6. Eval reports now include `Schema Violations`.
7. EvalRunner validates each actual tool call against the registered `ToolSpec.parameters`.
8. Schema violations are appended to eval errors and can fail the task when above threshold.
9. Added tests for missing required properties, type mismatch, enum violations, `oneOf`, schema-violation counting, and schema-violation threshold gating.

## Verification

```powershell
python -m pytest -q
# 154 passed, 2 skipped

python -m compileall -q metis
# passed
```

## External Reference Notes

1. Tool correctness evaluation systems treat correct parameters as part of agent quality, not a secondary implementation detail.
2. Tool-call validation guidance emphasizes catching missing required fields and wrong types at the tool boundary before side effects occur.
3. Recent function-calling evaluation work highlights missing parameters, incorrect parameter types, and instruction-format violations as practical agent failure modes.

## Remaining P0 Gaps

1. Schema validation is currently eval-only; dispatcher should also validate before executing tools.
2. The validator does not yet support `additionalProperties`, numeric ranges, string length, regex pattern, min/max items, or format.
3. Schema violations are counted as trajectory errors only when `max_schema_violations` is set; real 9B eval specs should set it to zero by default.
4. There is no repair loop yet for schema-invalid tool calls.
5. Tool schema validation errors are not yet classified into missing_required, type_mismatch, enum_violation, etc.
