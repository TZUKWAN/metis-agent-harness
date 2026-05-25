# Iteration 119 - Quality Gate Aware Targeted Eval Stubs

This iteration carries quality gate drift evidence into targeted eval stubs and materialized targeted suites.

## Problem

Iteration 118 made `eval compare` detect quality gate drift and write `quality_gate_changes` into diagnosis and repair tasks.

The next gap was repair execution. `build_eval_stubs_from_repair_tasks()` still generated a generic model-behavior stub. It did not preserve the gate name, gate metadata, or failure message in the executable targeted eval surface.

That made the repair loop weaker than the diagnosis. A repair agent could know that a gate failed only while reading `repair-tasks.json`; once materialized into a targeted suite, the gate-specific evidence became hard to recover.

## Changes

1. Targeted eval stubs now preserve:
   - `quality_gate_changes`
   - `quality_gate_names`
2. `eval_task_spec` now includes `quality_gates` when a repair task has gate drift.
3. Targeted eval prompts now include compact gate context:
   - task id;
   - gate name;
   - baseline pass state;
   - current pass state;
   - gate failure message;
   - gate metadata.
4. `suggested_assertion` for `quality_gate_failed` now requires the same gate inputs, metadata, and artifact expectations to pass after repair.
5. Stub Markdown now renders quality gate changes.
6. `materialize_eval_suite_from_stubs()` preserves quality gate drift payloads.
7. Materialized suite Markdown now renders quality gate changes.
8. `suite-schema-v1.json` now documents wrapped task metadata for:
   - `quality_gate_changes`
   - `quality_gate_names`
   - existing run/trust/stub wrapper fields.
9. `suite-schema.md` now describes quality gate drift metadata.

## Why This Matters

For small models, the harness needs to remove ambiguity from repair work.

Instead of asking a 9B model to infer why a broad quality failure happened, Metis now carries the exact gate drift into the generated regression task. The targeted eval can require the same gate to pass, which turns a soft quality issue into a deterministic repair target.

The repair path is now:

```text
quality gate result fails
-> compare detects gate drift
-> diagnosis records quality_gate_changes
-> repair task preserves quality_gate_changes
-> targeted eval stub preserves gate names and metadata
-> materialized suite requires the named quality gate
```

## Validation

- `python -m pytest tests\unit\test_eval_compare.py tests\unit\test_docs_exist.py -q`
- Result: `53 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Convert known gate metadata fields into concrete expected artifacts or required evidence constraints.
2. Standardize quality gate metadata schemas across all default gates.
3. Add release-gate checks for required gate presence.
4. Add dashboard trend views for gate-level drift.
5. Sign run attestations.
