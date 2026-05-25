# Iteration 117 - Model Quality Gate Results

This iteration persists quality gate results for normal model-behavior evals.

## Problem

Iteration 116 added `quality_gate_results` for deterministic artifact fixtures. Normal model tasks still only exposed gate failures as a count in `quality_failures`.

That was not enough for dashboards or repair agents. They need the gate name, pass/fail state, message, and metadata.

## Changes

1. `EvalRunner.run_task()` now records quality gate result payloads for model tasks.
2. `quality_failures` remains backward compatible:
   - missing expected artifacts;
   - missing required evidence sources;
   - failed quality gates.
3. `EvalResult.quality_gate_results` now covers:
   - deterministic fixtures;
   - provider-backed model evals.
4. Failure artifacts include:
   - `quality_gate_results`
5. Failure timelines include:
   - `quality.gate` events
6. Failure timeline Markdown renders quality gate events.
7. Eval report Markdown already has `## Quality Gate Results`; it now applies to all task types.

## Why This Matters

Quality gates are harness evidence. They should not be collapsed into a count.

The repair loop now has a direct path:

```text
model task fails quality gate
-> EvalResult.quality_gate_results
-> failure artifact quality_gate_results
-> timeline quality.gate event
-> diagnosis/repair can use gate name and metadata
```

This makes gate failures easier for a 9B model to understand and repair.

## Validation

- `python -m pytest tests\unit\test_eval_runner.py -q`
- Result: `40 passed`

## Remaining Gaps

1. Eval comparison should detect quality gate result drift.
2. Repair task generation should use gate names to choose owner areas and likely source modules.
3. Quality gate metadata schema should be standardized.
4. Attestation signing remains future work.
