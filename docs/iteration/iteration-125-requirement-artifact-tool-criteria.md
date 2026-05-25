# Iteration 125 - Requirement Artifact and Tool Criteria

Date: 2026-05-25

## Problem

`requirement_criteria` could express stable ids, evidence source type, evidence source ref, and minimum evidence strength. That was a major improvement over substring-only requirement coverage, but it still left an important production gap:

1. A model could mention that it delivered a file without the harness verifying the artifact record.
2. A model could describe a tool action without the harness verifying that the tool actually ran successfully.
3. Repair tasks could know a requirement failed, but not whether the missing evidence was a file, a tool call, or text/evidence coverage.

For a reusable agent harness, especially one intended to make small 9B/flash models reliable, acceptance criteria must bind to observed execution facts. The final answer is not enough. The verifier needs to inspect produced artifacts and tool trajectory records.

## Implementation

`requirements_covered_gate()` now supports two additional structured criterion fields:

- `required_artifact_path`
- `required_tool`

Aliases are also accepted:

- `artifact_path` -> `required_artifact_path`
- `tool_name` -> `required_tool`

The verifier now evaluates a criterion across four channels:

1. Final output text, for simple textual coverage.
2. Evidence records, with optional source type, source ref, and minimum strength.
3. Artifact records, with normalized path matching across Windows and POSIX separators.
4. Tool result records, requiring the named tool to have completed successfully.

Artifact path matching normalizes `\` to `/` before suffix comparison. This lets an eval suite declare `outputs/report.md` while runtime artifacts may be recorded as `C:\workspace\outputs\report.md`.

Tool verification treats a result as missing when the tool name does not appear or when the matching result is failed. A failed tool result cannot satisfy a delivery requirement.

## Gate Metadata

Failure metadata now includes:

- `missing_requirement_ids`
- `missing_requirements`
- `missing_artifact_paths`
- `missing_tools`
- `requirements`
- `requirement_criteria`
- `evidence_count`
- `artifact_count`

Successful metadata includes the same missing lists as empty arrays. That keeps dashboards and repair loops from needing defensive field checks.

## Harness Impact

This iteration moves Metis closer to contract-grade verification:

1. Acceptance criteria can require that a deliverable file exists in the observed artifact list.
2. Acceptance criteria can require that the correct tool was actually executed successfully.
3. Repair generation can distinguish content gaps from artifact gaps and trajectory gaps.
4. Small models are no longer trusted to self-report completion; the harness checks the external trace.

This is directly aligned with the infrastructure goal: Metis should be a reusable base for scenario-specific agents, where the scenario changes but the harness contract, evidence tracking, trajectory verification, and repair loop remain stable.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py -q
```

Result:

```text
48 passed
```

Related eval and validation coverage:

```powershell
python -m pytest tests\unit\test_quality_gates.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py tests\unit\test_eval_suite_validation.py tests\unit\test_eval_suite_run.py -q
python -m compileall -q metis
```

Result:

```text
137 passed
compileall passed
```

## Remaining Work

1. Add requirement-gap trend summaries to compare output and dashboards.
2. Validate `required_artifact_path` and `required_tool` references during suite validation instead of only at runtime.
3. Extend targeted eval generation so gate metadata containing missing artifact paths/tools becomes explicit `requirement_criteria`.
4. Add signed attestation for artifact bundles so artifact evidence is not only present but tamper-evident.
5. Add model-facing repair prompts that distinguish missing file evidence, missing successful tool evidence, and missing textual/evidence coverage.
