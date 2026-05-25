# Iteration 012 - Schema Repair Feedback

Date: 2026-05-25

## Goal

Small models frequently produce almost-correct tool calls: the tool name is right, but one required argument is missing or typed incorrectly. Iteration 011 blocked those calls before handler execution, which protected side effects, but the runtime feedback was still too generic for a 9B model to reliably self-correct.

This iteration turns schema validation failure into a recoverable control signal:

1. The dispatcher still blocks invalid arguments before the handler runs.
2. The agent loop now returns structured tool feedback with `error_type="schema_validation_failed"`.
3. The feedback includes the tool name, schema errors, original error, and a direct repair instruction.
4. The eval runner now measures schema repair attempts, successes, and failures.
5. Eval tasks can explicitly allow recovered schema failures when the goal is to measure self-repair instead of enforcing zero mistakes.

## Changes

### Runtime

File: `metis/runtime/loop.py`

Added `_tool_feedback_content()`:

- Normal tool results are passed through unchanged.
- Schema-invalid results are converted into structured JSON:
  - `error_type`
  - `tool`
  - `error`
  - `schema_errors`
  - `repair_instruction`

This makes the next model turn easier for small models because the previous failure is no longer just an opaque tool error. It becomes an explicit correction request.

### Evaluation

File: `metis/evals/runner.py`

Added task configuration:

- `min_schema_repair_successes`
- `max_schema_repair_failures`
- `allow_recovered_schema_failures`

Added result metrics:

- `schema_repair_attempts`
- `schema_repair_successes`
- `schema_repair_failures`

The eval runner counts a schema repair success when a schema-invalid call is followed later by a successful call to the same tool. By default, schema-invalid calls are still counted as tool failures. A task must explicitly set `allow_recovered_schema_failures=True` to evaluate recovery behavior without failing the whole task for the recovered invalid call.

### Tests

Added integration coverage:

- Invalid `write_file` call is blocked before handler side effects.
- The model receives structured schema repair feedback.
- A corrected second call executes successfully.

Added eval coverage:

- Recovered schema repair attempts are counted.
- Unrecovered schema repair attempts fail the configured repair gates.
- Recovered schema failures can be excluded from `tool_failures` only when the eval task explicitly enables that behavior.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
22 passed in focused tests
compileall passed
160 passed, 2 skipped in full test suite
```

## Remaining Risk

This iteration gives the model better feedback after schema failure, but it does not yet perform automatic argument repair outside the model loop. Future work should add:

1. Deterministic argument coercion for safe primitive cases, such as `"30"` to `30` when the schema requires integer.
2. Tool-specific repair prompts that include a compact schema excerpt.
3. Retry budgets per tool and per failure type.
4. Eval tasks that run against the real 9B/flash provider rather than only `FakeProvider`.
5. Trace events for schema repair attempts so dashboards can show which tools cause the most model friction.
