# Iteration 018 - Runtime and Command Shape Lineage

Date: 2026-05-25

## Goal

Iteration 017 added schema failure shape lineage. This iteration extends lineage to two more common small-model failure modes:

1. Runtime exceptions caused by lightly changed arguments.
2. Failed commands where the model changes only the target path or numeric value but repeats the same failing operation.

The intent is not to make the harness pessimistic. The intent is to stop obvious non-progress loops while still allowing materially different repairs.

## Changes

### Runtime Error Shape

File: `metis/runtime/loop.py`

Runtime errors now produce a normalized shape key:

```text
<exception_type>:<normalized_error_text>
```

Normalization replaces path-like and numeric fragments with placeholders. For example:

```text
RuntimeError: missing prerequisite 1
RuntimeError: missing prerequisite 2
```

both become:

```text
RuntimeError:runtimeerror: missing prerequisite <value>
```

This shape is stored in `failure_shape_key`. Runtime exception shape is currently recorded and used for retry-budget exhaustion metadata. It is not predicted pre-dispatch because the handler must run to know the exception.

### Command Semantic Shape

File: `metis/runtime/loop.py`

Command failures now get a lightweight semantic shape based on normalized command tokens:

- flags are ignored;
- numeric fragments become `<value>`;
- path-like fragments become `<path>`;
- the first two meaningful command tokens form the shape.

Examples:

```text
python -m pytest tests/a.py
python -m pytest tests/b.py
python -m pytest tests/c.py
```

all map to:

```text
python pytest
```

When this shape exhausts retry budget, later calls with the same semantic shape are blocked before dispatch as `retry_budget_exhausted`.

### Tool Feedback

Structured tool feedback now includes `failure_shape_key` when present. This gives the model a clearer reason why a repeated attempt is being rejected.

## Tests

Added integration coverage:

1. `run_test` fails for:
   - `python -m pytest tests/a.py`
   - `python -m pytest tests/b.py`
   - `python -m pytest tests/c.py`

   Under `small`, the third call is blocked before handler execution because all three share `python pytest`.

2. `fragile_tool` raises:
   - `RuntimeError("missing prerequisite 1")`
   - `RuntimeError("missing prerequisite 2")`

   Both runtime errors produce the same normalized shape key, and the second call exhausts retry budget.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_schema_guard.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
8 passed in focused integration tests
compileall passed
170 passed, 2 skipped in full test suite
```

## External References

OpenAI Agents SDK documents tool input guardrails as invocation-level checks that can reject a tool call before it executes. This supports Metis moving more repeat-loop protection into pre-dispatch control.

AutoGen documentation also treats termination conditions as stateful controls to stop long-running or non-progressing conversations. Metis lineage and retry budgets serve a similar purpose at the tool-call layer.

References:

- https://openai.github.io/openai-agents-js/guides/guardrails
- https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html

## Remaining Risk

The command semantic shape is intentionally conservative and simple. It can still over-block in some cases where the first two command tokens are the same but the later arguments materially change the operation. Future iterations should add:

1. Per-tool semantic shape functions.
2. Command-family-specific normalizers for `pytest`, `git`, `python`, `node`, and shell wrappers.
3. Cross-tool semantic lineage, such as `run_command` and `run_shell` attempting the same operation.
4. Eval metrics for blocked lineage by shape type.
5. Real-model evals to verify that 9B models recover by changing strategy rather than repeatedly changing filenames.
