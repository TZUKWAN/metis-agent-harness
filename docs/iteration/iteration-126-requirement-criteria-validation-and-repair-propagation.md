# Iteration 126 - Requirement Criteria Validation and Repair Propagation

Date: 2026-05-25

## Problem

Iteration 125 made `requirements_covered` capable of checking `required_artifact_path` and `required_tool` at runtime. That was necessary, but not sufficient for a production harness:

1. Bad criteria were still discovered late, during eval execution.
2. A criterion with only `required_tool` could not be represented naturally because the gate still required text.
3. `missing_artifact_paths` and `missing_tools` in quality gate metadata were not automatically compiled into the next targeted eval contract.

For a reusable agent harness, contract mistakes should fail before provider calls. Runtime failures should also become stronger repair tasks without a human rewriting the suite by hand.

## Implementation

### Quality Gate

`requirements_covered` now accepts structured criteria that are:

- text-only
- evidence-only
- artifact-only
- tool-only
- mixed text/evidence/artifact/tool criteria

A structured criterion is ignored only when it has no verifier field at all.

Tool-only criteria now work directly:

```json
{"id": "REQ-tool", "required_tool": "write_file"}
```

The gate still requires successful tool results; failed tool results do not satisfy `required_tool`.

### Suite Validation

`validate_eval_suite()` now validates `requirement_criteria` more deeply:

- every criterion entry must be an object;
- string fields must be non-empty strings when present;
- each criterion must declare at least one verifier field;
- `required_tool` and `tool_name` are checked against `available_tools` when a tool registry is supplied.

New validation codes:

- `empty_requirement_criterion`
- `invalid_type`
- `unknown_tool`

This moves common suite authoring mistakes from runtime failure into preflight validation.

### Targeted Eval Generation

`build_eval_stubs_from_repair_tasks()` now compiles quality gate metadata into executable criteria:

- `missing_artifact_paths=["outputs/report.md"]` becomes:

```json
{"id": "artifact:outputs/report.md", "required_artifact_path": "outputs/report.md"}
```

- `missing_tools=["write_file"]` becomes:

```json
{"id": "tool:write_file", "required_tool": "write_file"}
```

This means a failed runtime verifier can now generate a targeted repair eval that directly checks the artifact/tool gap that failed before.

## Harness Impact

This closes an important loop:

1. Suite authors can declare artifact/tool acceptance criteria.
2. Suite validation rejects malformed criteria before model execution.
3. Runtime gates report missing artifacts and tools in structured metadata.
4. Compare/repair generation converts that metadata back into executable eval contracts.
5. The next run verifies the exact missing artifact or tool trajectory instead of relying on prose.

For 9B/flash models, this matters because the model can stay focused on producing the next action while the harness handles precise contract enforcement. The small model is not trusted to self-certify completion.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_compare.py -q
python -m compileall -q metis
```

Result:

```text
77 passed
compileall passed
```

## Remaining Work

1. Extend compare summaries with requirement gap trends by requirement id, artifact path, and tool name.
2. Add dashboard panels for text/evidence/artifact/tool requirement gap classes.
3. Add suite validation for artifact path policy, such as rejecting parent traversal or absolute paths when a suite is meant to be portable.
4. Add signed artifact attestations so artifact evidence is tamper-evident across machines.
5. Expand real small-model eval suites with artifact-only and tool-only criteria.
