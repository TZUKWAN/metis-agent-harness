# Iteration 043 - Clustering from Task and Tool Signals

Date: 2026-05-25

## Objective

Improve failure clustering by using the richer failure artifacts produced in previous iterations.

The old clustering logic mostly used aggregate metrics, tool failure type counters, failure shape keys, and free-form errors. That was useful, but it missed two high-value sources:

- exact tool result metadata, especially schema errors and policy decisions;
- task contract metadata, especially required tools, forbidden tools, required order, and required arguments.

## Implemented

1. Clustering now reads `tool_result_excerpts`.

2. New cluster key families:
   - `schema_error:*`
   - `tool_policy_decision:*`

3. Clustering now reads `task_spec` plus trajectory errors.

4. New task-constraint cluster key families:
   - `task_constraint:required_tool_missing`
   - `task_constraint:forbidden_tool_used`
   - `task_constraint:tool_order_broken`
   - `task_constraint:tool_arguments_missing`
   - `task_constraint:evidence_source_missing`

5. Cluster signals now include:
   - task spec hashes
   - suite/model/profile run metadata
   - tool excerpt status
   - excerpt failure type
   - excerpt policy decision
   - excerpt failure shape key
   - schema errors

6. Remediation, severity, owner area, and suggested eval rules were extended for these new cluster families.

## Design Rationale

Production-grade harness diagnosis must distinguish:

- wrong tool selected;
- right tool with wrong arguments;
- forbidden tool called;
- required sequence skipped;
- policy denied;
- schema changed or prompt did not teach schema clearly enough.

These failures look similar in a flat pass/fail report. They require different fixes. The new cluster families create more actionable backlog items.

## External Calibration

Recent agent evaluation and observability systems emphasize the same direction:

- Future AGI Error Feed describes automatic clustering of production failures and taxonomy-based fixes.
- AgentRx emphasizes locating and categorizing critical failure steps in trajectories.
- Agent testing taxonomy discussions consistently separate tool choice, parameter handling, execution errors, and orchestration failures.

The Metis implementation remains deterministic and local-first, but the signal categories now align better with those production patterns.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_runner.py tests\unit\test_failure_clusters.py
```

Result:

```text
33 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Compare task hashes across baseline/current runs.

2. Link each comparison regression reason to:
   - affected task ids
   - failure artifact paths
   - cluster keys

3. Add a deterministic `failure-diagnosis.md` report that combines:
   - cluster summary
   - task contract
   - tool excerpt
   - suggested repair eval
