# Metis Eval Suite Schema

日期：2026-05-25

## 1. Purpose

This document defines the loadable Metis eval suite format consumed by:

- `metis.evals.runner.load_eval_task_specs()`
- `metis.evals.suite_run.load_eval_suite_payload()`
- `metis.evals.suite_validation.validate_eval_suite()`
- `metis eval run-suite`
- `metis eval validate-suite`

The schema exists because eval suites are long-lived harness assets. A suite may be generated from repair tasks, written by hand, reused across models, compared across runs, or migrated in future versions. The format must therefore be explicit, versioned, and validated before execution.

## 2. Supported Versions

Current supported schema versions:

- `1`

Machine-readable snapshot:

- `docs/evals/suite-schema-v1.json`

The authoritative code-level support set is:

```python
SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})
```

Validator behavior:

- Missing `schema_version` is a warning for legacy compatibility.
- Non-string `schema_version` is an error.
- Declared string versions outside the supported set are errors.

Generated materialized targeted suites must include:

```json
{
  "schema_version": "1"
}
```

## 3. Top-Level Object

A schema version 1 suite is a JSON object.

Required fields:

- `schema_version`: string. Must be `1` for version 1 suites.
- `tasks`: array. Must contain at least one eval task for runnable suites.

Recommended fields:

- `suite`: string. Stable suite name, such as `targeted-repair-regression`.
- `profile`: string. Intended comparison or execution profile, such as `release`.
- `task_count`: integer. Count of task entries. Consumers should prefer `len(tasks)` when validating.
- `baseline`: object. Optional baseline run metadata.
- `current`: object. Optional current run metadata.
- `artifact_path_diagnostic_summary`: object. Aggregated counts for filtered artifact path diagnostics across all tasks. Generated stubs and materialized suites include `total`, `by_reason`, `by_source`, `by_gate`, and `by_task`.

Generated targeted suites currently use:

```json
{
  "suite": "targeted-repair-regression",
  "schema_version": "1",
  "profile": "release",
  "baseline": {},
  "current": {},
  "task_count": 1,
  "tasks": []
}
```

## 4. Task Entry Forms

Version 1 supports two task entry forms.

### 4.1 Wrapped Task Entry

Generated repair-regression suites use a wrapper object with repair metadata plus a nested `task_spec`.

Required for execution:

- `task_spec`: object. Must be a valid `EvalTaskSpec`.

Recommended wrapper metadata:

- `task_id`: string. Mirrors `task_spec.id`.
- `source_repair_task_id`: string.
- `reason`: string.
- `priority`: string.
- `owner_area`: string.
- `cluster_keys`: array of strings.
- `critical_event_ids`: object mapping run or task ids to event ids.
- `run_metadata`: object. Source run provenance anchors carried from diagnosis.
- `stub_type`: string. Generated stubs use `model_behavior` or `artifact_verification`.
- `trust_state`: object. Optional structured trust failures from comparison.
- `target_runs`: array of strings. Artifact verification fixtures use this to identify baseline/current sides.
- `quality_gate_changes`: array of objects. Gate drift payloads copied from comparison diagnosis.
- `quality_gate_names`: array of strings. Compact gate names extracted from `quality_gate_changes`.
- `missing_requirements`: array of strings. Requirement coverage gaps extracted from quality gate metadata.
- `artifact_path_diagnostics`: array of objects. Non-portable artifact paths filtered out while compiling quality gate metadata into executable eval contracts. Each entry includes the source field, original path, and rejection reason.
- `schema_repair_hint_events`: object.
- `schema_repair_hint_types`: array of strings.
- `schema_repair_argument_templates`: array of objects.
- `tool_schemas`: object mapping tool names to JSON schemas.
- `likely_source_modules`: array of strings.
- `suggested_assertion`: string.
- `verification_command`: string.

Example:

```json
{
  "task_id": "targeted-repair-001",
  "source_repair_task_id": "repair-001",
  "reason": "schema_repair_hint_type_failures_increased",
  "priority": "critical",
  "owner_area": "tool-schema-and-repair",
  "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
  "critical_event_ids": {"current": "current:002:schema.repair_hint"},
  "quality_gate_changes": [],
  "quality_gate_names": [],
  "missing_requirements": [],
  "schema_repair_hint_types": ["add_required_property"],
  "schema_repair_argument_templates": [],
  "tool_schemas": {
    "crm_update": {
      "type": "object",
      "properties": {
        "customer_id": {"type": "integer", "minimum": 1000}
      }
    }
  },
  "likely_source_modules": ["metis/tools/schema_validator.py"],
  "suggested_assertion": "Schema repair hint recovery succeeds.",
  "verification_command": "python -m pytest tests/unit/test_eval_compare.py -q",
  "task_spec": {
    "id": "targeted-repair-001",
    "prompt": "Recover from schema failure.",
    "allowed_tools": ["write_file"],
    "max_turns": 4,
    "max_schema_violations": 0
  }
}
```

### 4.2 Direct EvalTaskSpec Entry

Handwritten suites may put `EvalTaskSpec` objects directly in `tasks`.

Example:

```json
{
  "id": "direct-001",
  "prompt": "Read the README and summarize it.",
  "allowed_tools": ["read_file"],
  "max_turns": 4
}
```

Direct entries are valid, but generated repair suites should prefer wrapped entries so diagnosis and repair lineage remain auditable.

## 5. EvalTaskSpec Fields

`task_spec` must match `metis.evals.runner.EvalTaskSpec`.

Required fields:

- `id`: non-empty string.
- `prompt`: non-empty string.

Tool and artifact fields:

- `allowed_tools`: array of non-empty strings.
- `expected_artifacts`: array of non-empty portable relative artifact paths. Absolute paths, Windows drive-prefixed paths, and parent traversal are rejected by suite validation.
- `required_tools`: array of non-empty strings.
- `forbidden_tools`: array of non-empty strings.
- `required_tool_order`: array of non-empty strings.
- `required_tool_arguments`: array of objects.
- `required_evidence_sources`: array of non-empty strings.
- `requirements`: array of non-empty strings. Acceptance criteria that gates can verify against final output, evidence, and artifact records.
- `requirement_criteria`: array of objects. Structured acceptance criteria with optional `id`, `text`, `required_source_type`, `required_source_ref`, `min_strength`, `required_artifact_path`, and `required_tool`. `artifact_path` is accepted as an alias for `required_artifact_path`; `tool_name` is accepted as an alias for `required_tool`. A criterion may be text-only, evidence-only, artifact-only, tool-only, or a combination, but it must declare at least one verifier field. Suite validation checks that string fields are non-empty strings, that artifact paths are portable relative paths, and, when an active tool registry is supplied, that `required_tool` / `tool_name` references a known tool.
- `quality_gates`: array of non-empty strings.

Execution and quality fields:

- `fixture_type`: string. Empty for normal model behavior tasks; `artifact_verification` for deterministic run-bundle checks.
- `requires_model_execution`: boolean. Defaults to `true`. When `false`, `EvalRunner` must not call the provider.
- `artifact_verification`: object. Deterministic fixture configuration, including `target_runs`, `target_run_dirs`, `trust_state`, and required checks.
- `max_turns`: integer, at least 1.
- `require_verified_final`: boolean.
- `max_duplicate_tool_calls`: integer or null.
- `max_invalid_tool_calls`: integer or null.
- `max_policy_blocks`: integer or null.
- `max_evidence_resolution_failures`: integer or null.
- `max_schema_violations`: integer or null.
- `min_schema_repair_successes`: integer or null.
- `max_schema_repair_failures`: integer or null.
- `allow_recovered_schema_failures`: boolean.
- `min_schema_repair_hint_successes`: integer or null.
- `max_schema_repair_hint_failures`: integer or null.
- `min_tool_repair_successes`: integer or null.
- `max_tool_repair_failures`: integer or null.
- `allow_recovered_tool_failures`: boolean.
- `max_retry_budget_exhaustions`: integer or null.
- `max_pre_dispatch_blocks`: integer or null.
- `required_failure_shape_keys`: array of non-empty strings.
- `forbidden_failure_shape_keys`: array of non-empty strings.
- `max_failure_shape_key_counts`: object mapping failure shape keys to counts.

Unknown `EvalTaskSpec` fields are warnings. They are ignored by the runner.

### 5.1 Artifact Verification Fixtures

Artifact verification fixtures are deterministic harness checks, not model behavior tasks.

They use:

```json
{
  "id": "artifact-verification-repair-001",
  "prompt": "Verify artifact integrity for the untrusted Metis eval run bundle.",
  "fixture_type": "artifact_verification",
  "requires_model_execution": false,
  "allowed_tools": [],
  "max_turns": 1,
  "quality_gates": ["run_attestation_verifies"],
  "artifact_verification": {
    "target_runs": ["current"],
    "target_run_dirs": {"current": "docs/evals/runs/current"},
    "required_checks": [
      "run-attestation.json exists",
      "all attestation subjects exist",
      "subject sha256 digests match local bytes",
      "subject sizes match local bytes"
    ]
  }
}
```

When `target_run_dirs` is absent, loaders may enrich it from top-level `baseline.run_dir` and `current.run_dir` using `target_runs`.

`metis eval run-suite` may run suites composed only of `requires_model_execution=false` fixtures without provider environment variables. Mixed suites still require a configured provider because at least one task needs model execution.

## 6. Required Tool Arguments

`required_tool_arguments` entries constrain the tool calls that must appear in a successful run.

Each entry may use:

- `tool` or `tool_name`: string.
- `arguments` or `args`: object.

Argument expectations may be literals or predicates.

Supported predicate keys:

- `equals`
- `contains`
- `startswith`
- `endswith`
- `in`

Example:

```json
{
  "tool": "write_file",
  "arguments": {
    "path": {
      "contains": "outputs/metis-placeholder.txt"
    }
  }
}
```

When tool schemas are supplied to `validate_eval_suite()`, argument names and predicate value types are checked against the referenced tool schema.

## 7. Schema Repair Metadata

Version 1 repair metadata is diagnostic and audit-oriented. It should not change runtime task execution unless the metadata is also reflected in `task_spec`.

Important generated metadata:

- `schema_repair_hint_events`: timeline-derived event payloads.
- `schema_repair_hint_types`: stable hint type names.
- `schema_repair_argument_templates`: malformed/corrected argument template pairs.

The current generator also injects schema repair argument templates into `task_spec.prompt` and derives `required_tool_arguments` from corrected templates.

## 8. Compatibility Rules

Version 1 compatibility policy:

- Adding optional top-level fields is backward compatible.
- Adding optional wrapper metadata fields is backward compatible.
- Adding optional `EvalTaskSpec` fields requires runner and validator support before suites use them.
- Removing required fields is breaking.
- Changing the meaning of an existing field is breaking.
- Tightening validator rules can be breaking for handwritten suites and must be documented.
- Unknown declared `schema_version` values are rejected.

## 9. Migration Rules

No migrations are currently implemented.

Future migrations should:

1. Add a version-aware load path before introducing breaking version 2 suites.
2. Preserve the original suite file when writing migrated output.
3. Emit a migration report with source version, target version, changed fields, and warnings.
4. Keep generated repair lineage fields intact unless explicitly superseded.
5. Add tests for old suite, migrated suite, validation report, and runner behavior.

## 10. Release Gate Expectations

Release and strict profiles should eventually enforce:

- generated suites include `schema_version`;
- declared versions are supported;
- unversioned suites are not used for release comparisons unless explicitly waived;
- runner reports include the consumed suite version;
- comparison reports include suite version drift when baseline and current runs used different suite schema versions.
