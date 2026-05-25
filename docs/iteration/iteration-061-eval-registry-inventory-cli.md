# Iteration 061 - Eval Registry Inventory CLI

## Purpose

Iteration 060 made suite validation registry-aware. Iteration 061 makes those registries discoverable from the CLI.

Suite authors should not need to inspect Python code to know which tools and quality gates can be referenced in `EvalTaskSpec`. The harness now exposes the active built-in tool registry and default quality gate registry through eval commands.

## Research Basis

Current eval tooling often exposes inventory commands for graders, extractors, validators, or components. That pattern matters for agent harnesses because suite definitions are declarative: authors need to discover valid component names before writing eval specs.

Metis applies the same idea to:

- tool names used by trajectory constraints;
- quality gate names used by eval task specs.

## Implemented

1. Tool inventory API:
   - `generic_eval_tool_inventory(workspace=...)`
   - `tool_inventory_to_markdown(inventory)`

2. Quality gate inventory API:
   - `generic_eval_quality_gate_inventory()`
   - `quality_gate_inventory_to_markdown(inventory)`

3. CLI:

```bash
metis eval list-tools --workspace <workspace>
metis eval list-tools --workspace <workspace> --json
metis eval list-quality-gates
metis eval list-quality-gates --json
```

## Tool Inventory Fields

Each tool entry includes:

- `name`
- `description`
- `category`
- `side_effect`
- `requires_permission`
- `retry_policy`
- `verification`
- `metadata`
- `parameters`

The JSON output is intended for CI and suite-authoring tools. The Markdown output is intended for human review.

## Quality Gate Inventory Fields

Each gate entry includes:

- `name`
- `description`
- `failure_policy`
- `metadata`

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py tests/unit/test_eval_suite_validation.py -q
```

Result:

```text
51 passed
```

## Remaining Gaps

1. Inventory currently lists built-in tools and default quality gates only.
2. Plugin and adapter registries need a unified construction path so inventory and runtime execution use the exact same registry.
3. Tool inventory does not yet include a compact schema summary for required argument fields.
4. Quality gate inventory does not yet include expected context keys.
5. Suite validation still does not cross-check required argument predicates against tool JSON schemas.
