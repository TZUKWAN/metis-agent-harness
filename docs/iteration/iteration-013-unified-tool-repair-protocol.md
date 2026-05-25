# Iteration 013 - Unified Tool Repair Protocol

Date: 2026-05-25

## Goal

Iteration 012 made schema validation failures recoverable by returning structured repair feedback to the model. That solved only one failure mode. A production harness for 9B models needs every tool failure to be typed, auditable, and actionable.

This iteration introduces a unified tool failure protocol. The protocol is deliberately simple enough for small models:

1. Every blocked/error tool result should expose a stable `failure_type`.
2. The runtime should say whether the failure is recoverable.
3. The runtime should say whether retry is allowed.
4. The runtime should provide a short repair instruction.
5. The agent loop should return this structured feedback to the model as tool output.
6. The eval runner should be able to count failure types.

This follows the same general harness principle used by modern agent systems: guardrails must wrap tool invocation, not just final output. OpenAI Agents SDK documents tool guardrails as checks that can allow execution, reject content with a message, or throw a tripwire. Metis now has the first internal version of that control surface.

## New Module

File: `metis/tools/failures.py`

Added `ToolFailureType`:

- `unknown_tool`
- `tool_not_allowed`
- `schema_validation_failed`
- `policy_denied`
- `approval_required`
- `unsafe_command`
- `guardrail_blocked`
- `hook_blocked`
- `command_failed`
- `runtime_error`

Added `tool_failure_metadata()` which returns:

- `failure_type`
- `recoverable`
- `retry_allowed`
- `repair_instruction`

## Dispatcher Integration

File: `metis/tools/dispatcher.py`

Structured failure metadata is now attached to:

- Unknown tool calls.
- Tool not allowed by context.
- Policy denied calls.
- Approval-required calls.
- Dangerous shell command blocks.
- Small-model guardrail blocks.
- Hook blocks.
- Schema validation failures.
- Non-zero command exits.
- Handler runtime exceptions.

This makes tool failures machine-readable. The model sees a consistent feedback object, and eval/reporting code no longer needs to infer behavior only from fragile error strings.

## Agent Loop Integration

File: `metis/runtime/loop.py`

`_tool_feedback_content()` now checks `ToolResult.metadata["failure_type"]`.

When present, the tool message sent back to the model becomes structured JSON:

- `error_type`
- `tool`
- `status`
- `error`
- `recoverable`
- `retry_allowed`
- `repair_instruction`
- optional `schema_errors`
- optional `policy_decision`
- optional `risk_level`
- optional `exit_code`

For normal successful tool calls, the existing content is passed through unchanged.

## Eval Integration

File: `metis/evals/runner.py`

Added `EvalResult.tool_failure_types`, a dictionary counting failure types observed in a run.

This is intentionally broad. It can support future scorecards such as:

- Model invented tools.
- Model violated tool allowlists.
- Model repeatedly failed schema.
- Model hit policy blocks.
- Tool runtime failures.
- Command failures.

## Tests Added or Extended

Updated tests cover:

- Unknown tool returns repair metadata.
- Hook block returns `hook_blocked`.
- Runtime exception returns `runtime_error`.
- Context allowlist block returns `tool_not_allowed`.
- Non-zero command returns `command_failed`.
- Schema validation block returns `schema_validation_failed`.
- Dangerous shell command returns `unsafe_command`.
- Approval-required command returns `approval_required`.
- AgentLoop emits structured runtime error feedback.
- EvalRunner counts `tool_failure_types`.

## Verification

Commands run:

```powershell
python -m pytest -q tests\unit\test_tools.py tests\unit\test_tool_policy.py tests\integration\test_agent_loop_schema_guard.py tests\unit\test_eval_runner.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
38 passed in focused tests
compileall passed
163 passed, 2 skipped in full test suite
```

## Remaining Risk

This is still the first version of the repair protocol. The next upgrades should be:

1. Add retry budgets per `failure_type`.
2. Add generic repair success metrics for all recoverable failure types, not just schema.
3. Add tool-specific repair policies, because a failed `run_test` should not be repaired the same way as a failed `write_file`.
4. Add trace events for `failure_type`, `recoverable`, and `retry_allowed`.
5. Add real-model evals that measure whether 9B/flash models actually use the repair instruction correctly.
6. Add non-bypass rules so unsafe commands and approval-required actions cannot be retried with disguised wording.
