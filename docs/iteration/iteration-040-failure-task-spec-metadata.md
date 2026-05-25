# Iteration 040 - Failure Task Spec Metadata

Date: 2026-05-25

## Objective

Make failed eval artifacts self-contained enough for automated diagnosis and later repair-data generation.

Before this iteration, a failed task artifact contained metrics and errors, but it did not preserve the task's original constraints. That made triage weaker: a cluster could say a task failed because of a missing tool, schema violation, or evidence issue, but the artifact did not directly show the prompt, required tools, forbidden tools, evidence policy, or gate thresholds that defined success.

## Implemented

1. `EvalSuiteResult` now carries an optional `task_specs` map:
   - key: task id
   - value: `EvalTaskSpec`

2. `EvalRunner.run_suite()` now populates the `task_specs` map automatically.

3. Failure artifacts now include `task_spec` when available.

4. `failures/index.json` artifact entries now include:
   - `has_task_spec`

5. The serialized task spec includes:
   - id
   - prompt
   - allowed tools
   - max turns
   - expected artifacts
   - required evidence sources
   - quality gates
   - verified-final requirement
   - required tools
   - forbidden tools
   - required tool order
   - required tool arguments
   - duplicate/invalid/policy/evidence/schema/tool-repair/retry/pre-dispatch thresholds
   - failure shape requirements

## Design Rationale

Failure clusters become much more useful when the failing task's contract is present next to the observed failure.

This enables future automation to answer:

- Did the model violate a required tool?
- Did it use a forbidden tool?
- Did it satisfy the evidence policy?
- Was the task expecting schema repair?
- Was the retry budget too strict?
- Did the prompt make the required sequence clear?
- Which exact task contract should be turned into a repair eval?

For a 9B-model harness, this metadata is especially important because most improvements should happen at the harness layer: clearer task contracts, better tool feedback, more precise repair instructions, and stronger finalization gates.

## Validation

Targeted test:

```bash
python -m pytest -q tests\unit\test_eval_runner.py
```

Result:

```text
29 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add compact tool-result excerpts to each failed task artifact:
   - tool name
   - status
   - failure type
   - recoverable flag
   - retry metadata
   - schema errors
   - short content/error preview

2. Add prompt/instruction hash to task spec metadata.

3. Add provider/model/run environment metadata to each failure artifact.

4. Teach failure clustering to use task-spec constraints as signals, for example:
   - required tool missing
   - forbidden tool used
   - required evidence source missing
   - required tool order broken
