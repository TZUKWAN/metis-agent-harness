# Iteration 118 - Quality Gate Drift Compare

This iteration makes `eval compare` detect quality gate result drift.

## Problem

Iterations 116 and 117 persisted `quality_gate_results` for deterministic artifact fixtures and normal model-behavior evals. The remaining gap was comparison.

Without comparison support, a run could keep `success=True` and keep numeric metrics stable while a delivery gate moved from pass to fail. That is a real regression for Metis because the harness goal is not merely task completion. It is audited, evidence-backed, high-quality delivery.

## Changes

1. `compare_eval_runs()` now computes `quality_gate_diff`.
2. `quality_gate_diff` includes:
   - `new_failed_gates`
   - `resolved_failed_gates`
3. Each quality gate change records:
   - task id;
   - gate name;
   - baseline pass state;
   - current pass state;
   - failure message;
   - gate metadata.
4. Release and strict profiles now emit:
   - `quality_gate_failed`
5. Regression reason links for `quality_gate_failed` include:
   - task ids;
   - failure artifacts;
   - failure timelines;
   - structured `quality_gate_changes`.
6. Comparison Markdown now includes:
   - `## Quality Gate Drift`
   - formatted gate changes such as `a.markdown_report`
7. Diagnosis entries preserve `quality_gate_changes`.
8. Diagnosis Markdown renders quality gate changes.
9. Repair tasks preserve `quality_gate_changes`.
10. Repair routing now maps `quality_gate_failed` to:
    - owner area: `quality-gates-and-evidence`
11. Suggested eval text now asks for a deterministic reproduction of the gate input and requires the gate to pass.
12. Likely source module inference now includes quality-gate modules:
    - `metis/quality/gates.py`
    - `metis/quality/runner.py`
    - `metis/evals/runner.py`
    - `metis/evals/compare.py`
    - `metis/evidence/ledger.py`

## Why This Matters

Small models often fail softly. They may produce an answer that looks complete, while missing a required heading, evidence reference, artifact, attestation, or format guarantee.

Quality gates encode those delivery expectations. Treating gate drift as a regression means Metis can block degraded deliverables even when the model appears to have completed the task.

This also improves automated repair. The repair loop receives a gate name and metadata instead of a vague quality failure count.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `49 passed`
- `python -m compileall -q metis`
- Result: passed

## Remaining Gaps

1. Standardize quality gate metadata schemas.
2. Carry quality gate names and metadata into targeted eval stubs.
3. Add dashboard trend views for gate-level pass/fail drift.
4. Add release-gate support for required gate presence, not only gate pass/fail.
5. Add signed attestations for run bundles.
