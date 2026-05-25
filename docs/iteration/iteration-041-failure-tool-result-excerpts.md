# Iteration 041 - Failure Tool Result Excerpts

Date: 2026-05-25

## Objective

Make failed eval artifacts useful without requiring a full trace open for the first diagnostic pass.

Task specs explain what the model was supposed to do. Tool result excerpts explain what actually happened at the tool boundary. Together, they make failure artifacts suitable for clustering, backlog generation, and future repair datasets.

## Implemented

1. `EvalResult` now includes:
   - `tool_result_excerpts`

2. `EvalRunner.run_task()` now records compact excerpts from tool results.

3. Failure artifacts now include:
   - `tool_result_excerpts`

4. Each excerpt includes:
   - index
   - tool name
   - tool call id
   - status
   - failed flag
   - selected metadata
   - content preview
   - error preview

5. Selected metadata includes:
   - failure type
   - recoverable flag
   - retry allowed
   - retry budget exhausted
   - pre-dispatch block
   - schema valid
   - schema errors
   - failure shape key
   - policy decision
   - repair instruction

6. Excerpts are bounded:
   - first 20 tool results
   - 500 characters per content/error preview

## Design Rationale

Full traces are necessary for deep debugging, but they are too heavy for first-pass triage and clustering.

A compact excerpt gives automated systems enough signal to answer:

- which tool failed;
- whether the failure was schema, policy, runtime, retry, or guardrail related;
- whether the model received a repair instruction;
- whether a repeated failure shape was involved;
- whether the tool result was blocked before dispatch;
- what short error text should be shown in reports.

For a 9B harness, this matters because repair quality depends on clear, compact feedback. The same compact signals can later be used to build repair prompts and eval cases.

## Validation

Targeted test:

```bash
python -m pytest -q tests\unit\test_eval_runner.py
```

Result:

```text
30 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Add task spec and prompt hashes:
   - prompt hash
   - constraints hash
   - task spec hash

2. Add provider/model/run environment metadata to failure artifacts.

3. Teach clustering to use tool-result excerpt metadata directly:
   - failure type
   - schema errors
   - policy decision
   - failure shape key
   - retry exhausted

4. Link compare regression reasons back to specific failed task artifacts and cluster artifacts.
