# Iteration 048 - Eval Diagnose CLI and Repair Tasks

Date: 2026-05-25

## Objective

Make comparison diagnosis actionable from the CLI.

The previous iteration produced `diagnosis.json` and `diagnosis.md`. This iteration turns those diagnosis entries into repair task stubs that can feed the next improvement loop.

## Implemented

1. Added diagnosis loading:
   - `load_eval_diagnosis()`

2. Added repair task generation:
   - `build_repair_tasks_from_diagnosis()`
   - `repair_tasks_to_markdown()`
   - `write_repair_tasks()`
   - `diagnose_eval_comparison()`

3. Added CLI:
   - `metis eval diagnose --comparison <comparison-dir>`
   - `metis eval diagnose --comparison <comparison-dir> --output-dir <repair-dir>`
   - `metis eval diagnose --comparison <comparison-dir> --json`

4. `diagnose_eval_comparison()` writes:
   - `repair-tasks.json`
   - `repair-tasks.md`

5. Repair task stubs include:
   - id
   - reason
   - priority
   - owner area
   - task ids
   - cluster keys
   - artifact paths
   - fields
   - metrics
   - changes
   - recommended action
   - suggested eval
   - source backlog items

6. Cluster-linked diagnosis entries are enriched from the current run's remediation backlog when available:
   - severity -> repair priority
   - owner area
   - recommended action
   - suggested eval
   - remediation item id

## Design Rationale

The harness should not stop at detecting regressions. It should produce the next repair queue.

This mirrors the operational pattern seen in evaluation-driven remediation systems:

1. Run evals.
2. Compare against baseline.
3. Diagnose failures.
4. Map failure patterns to remediation strategies.
5. Add or update eval coverage.
6. Verify the repair.

Metis now has the first concrete bridge from comparison diagnosis into repair planning.

## External Calibration

This direction matches current evaluation-driven triage guidance: start from actual failing cases, map failure patterns to remediation strategies, and generate fix plans from trace/eval evidence. Sources reviewed this iteration included Microsoft Copilot Studio evaluation triage guidance, Corbell failure-driven eval automation, Future AGI Error Feed, and AgentRx.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
```

Result:

```text
36 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Link repair task stubs to concrete harness components:
   - tool schema and repair
   - runtime lineage and recovery
   - evidence and finalization
   - eval oracles and prompts

2. Add `metis eval repair-plan`:
   - groups repair tasks by owner area
   - orders by priority
   - emits verification commands

3. Add trace timeline export so repair tasks can point to exact tool call or finalization step.
