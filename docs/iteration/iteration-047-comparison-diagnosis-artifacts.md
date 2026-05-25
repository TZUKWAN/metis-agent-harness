# Iteration 047 - Comparison Diagnosis Artifacts

Date: 2026-05-25

## Objective

Turn comparison reason links into standalone diagnosis artifacts.

Reason links are useful inside `comparison.json`, but downstream automation should not need to understand the entire comparison schema to create repair tasks. A diagnosis artifact gives the repair loop a smaller, action-oriented input.

## Implemented

1. Added `eval_run_comparison_diagnosis()`.

2. Added `eval_run_diagnosis_to_markdown()`.

3. `write_eval_run_comparison()` now writes:
   - `comparison.json`
   - `comparison.md`
   - `diagnosis.json`
   - `diagnosis.md`

4. Each diagnosis entry includes:
   - reason
   - task ids
   - cluster keys
   - artifact paths
   - changed environment/task fields
   - metric deltas
   - task spec changes
   - recommended action

## Design Rationale

The comparison report is for humans and CI. The diagnosis report is for repair planning.

This separation matters because future repair automation should read a compact, stable shape:

- what failed;
- where the evidence is;
- which cluster or task is affected;
- what action should be attempted first.

That turns eval comparison into an active improvement loop rather than a passive report.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
```

Result:

```text
19 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add CLI command:
   - `metis eval diagnose --comparison <comparison-dir>`

2. Link diagnosis entries to remediation backlog items.

3. Generate repair task stubs:
   - owner area
   - suggested eval
   - affected files/components
   - verification command
