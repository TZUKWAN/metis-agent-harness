# Iteration 060 - Registry-Aware Suite Validation

## Purpose

Iteration 059 validated eval suite structure. Iteration 060 validates suite references against the active harness registries.

This matters because a structurally valid suite can still be impossible to run: it may reference a tool that does not exist in the current workspace or a quality gate that is not registered. Those failures should be caught before model calls, not discovered during an expensive run.

## Research Basis

Current agent-eval and pre-execution safety practice emphasizes:

- validating named components before execution;
- listing available graders/verifiers/extractors;
- checking tool identity against a registry;
- keeping deterministic pre-execution checks separate from LLM judge scoring.

Metis applies the same idea to eval suites: task specs now validate declared tools and quality gates against the actual harness registries used by `run-suite`.

## Implemented

1. Registry-aware validation inputs:
   - `validate_eval_suite(path, available_tools=..., available_quality_gates=...)`

2. Generic validation context:
   - `generic_eval_validation_context(workspace=...)`
   - builds the active built-in tool registry for the workspace;
   - reads default quality gate names from `QualityGateRunner`.

3. `run-suite` integration:
   - validates with active tool names;
   - validates with active quality gate names;
   - still validates before endpoint checks and model calls.

4. `validate-suite` integration:

```bash
metis eval validate-suite --suite <suite-json-or-dir> --workspace <workspace>
```

The workspace controls the active tool registry used for validation.

## Validation Rules Added

Tool references are checked in:

- `allowed_tools`
- `required_tools`
- `forbidden_tools`
- `required_tool_order`
- `required_tool_arguments[*].tool`
- `required_tool_arguments[*].tool_name`

Quality gate references are checked in:

- `quality_gates`

List item typing is now stricter:

- list fields such as `allowed_tools`, `quality_gates`, `required_tools`, `forbidden_tools`, and artifact/evidence lists must contain non-empty strings;
- `required_tool_arguments` remains a list of objects and is validated with its own rules.

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_eval_suite_validation.py tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py -q
```

Result:

```text
45 passed
```

## Remaining Gaps

1. Registry-aware validation currently covers built-in tools; plugin/adapter-provided tools need a shared registry construction path.
2. Quality gate validation covers default gates; plugin/adapter-provided gates need the same shared construction path.
3. The validation report does not yet include available tool/gate inventory.
4. There is no `metis eval list-tools` or `metis eval list-quality-gates` command yet.
5. Tool argument validation checks object shape but does not yet validate required argument predicates against each tool's JSON schema.
