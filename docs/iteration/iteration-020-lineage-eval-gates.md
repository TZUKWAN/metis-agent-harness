# Iteration 020 - Lineage Eval Gates

Date: 2026-05-25

## Goal

Iteration 019 made lineage behavior visible in eval reports. Visibility is not enough for a production harness. Real 9B eval suites need hard gates that fail a task when the agent is looping, repeatedly exhausting retry budgets, or hitting known-bad failure shapes.

This iteration turns lineage metrics into configurable eval gates.

## Changes

### Eval Task Spec

File: `metis/evals/runner.py`

Added:

- `max_retry_budget_exhaustions`
- `max_pre_dispatch_blocks`
- `required_failure_shape_keys`
- `forbidden_failure_shape_keys`
- `max_failure_shape_key_counts`

These follow the existing trajectory gate pattern. They are opt-in, so existing eval tasks keep their behavior.

### Trajectory Errors

`_trajectory_errors()` now emits failures when:

- retry budget exhaustions exceed a threshold;
- pre-dispatch blocks exceed a threshold;
- required failure shape keys are absent;
- forbidden failure shape keys are observed;
- a specific failure shape appears more than allowed.

Example:

```python
EvalTaskSpec(
    id="lineage-thresholds",
    prompt="run",
    max_retry_budget_exhaustions=1,
    max_pre_dispatch_blocks=0,
    forbidden_failure_shape_keys=["python pytest"],
    max_failure_shape_key_counts={"python pytest": 2},
)
```

This fails when a model keeps repeating the same failing pytest command pattern.

### Report Coverage

The eval report already included:

- Retry Budget Exhaustions
- Pre-dispatch Blocks

This iteration adds test coverage that verifies those columns exist in the generated markdown report.

## Tests

Added tests for:

1. Lineage threshold enforcement:
   - `max_retry_budget_exhaustions`
   - `max_pre_dispatch_blocks`
   - `forbidden_failure_shape_keys`
   - `max_failure_shape_key_counts`

2. Required failure shape keys:
   - task fails when a required shape is missing.

3. Markdown report fields:
   - report includes `Retry Budget Exhaustions`;
   - report includes `Pre-dispatch Blocks`.

## Verification

Commands run:

```powershell
python -m pytest -q tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
25 passed in focused eval tests
compileall passed
173 passed, 2 skipped in full test suite
```

## External References

LangChain AgentEvals documents trajectory evaluation as a first-class evaluation mode. OpenAI Evals similarly treats evals as reusable tests for model behavior. Metis lineage gates extend that idea to harness-level loop and tool-failure behavior, which is especially important for small models.

References:

- https://docs.langchain.com/oss/python/langchain/evals
- https://platform.openai.com/docs/guides/evals

## Remaining Risk

Lineage gates are now available, but the project still lacks a real 9B/flash benchmark suite that uses them by default. The next iteration should start building a real-model eval suite with strict default gates:

1. `max_schema_violations=0`
2. `max_retry_budget_exhaustions=0`
3. `max_pre_dispatch_blocks=0`
4. `max_tool_repair_failures=0`
5. `require_verified_final=True` where evidence is expected
