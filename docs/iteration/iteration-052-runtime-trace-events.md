# Iteration 052 - Runtime Trace Events

## Goal

Previous iterations created failed-task timelines and a CLI viewer, but the timeline was mostly derived from final eval result data. This iteration starts capturing runtime-native trace events inside `AgentLoop` and carries them into eval failure timelines.

## Implemented

1. `AgentRunResult` now includes:
   - `trace_events`

2. `AgentLoop` now records runtime trace events:
   - `agent.start`
   - `model.request`
   - `model.response`
   - `parser.repair.request`
   - `parser.repair.result`
   - `tool.request`
   - `tool.result`
   - `finalization.check`
   - `finalization.result`
   - `finalization.repair.request`
   - `finalization.repair.result`
   - `agent.error`

3. Runtime trace events include stable event ids:
   - `<session-id>:<index>:<event-type>`

4. Runtime trace events carry structured attributes:
   - turn number
   - status
   - tool name
   - tool call id
   - model operation marker
   - tool operation marker
   - usage
   - finish reason
   - parser repair attempt
   - finalization verification result
   - tool metadata

5. `EvalResult` now carries:
   - `trace_events`

6. Failed eval timelines now prefer runtime trace events when available and fall back to synthetic task/tool/error events when not available.

7. Timeline rendering now summarizes nested runtime attributes, including:
   - failure type
   - policy decision
   - failure shape key
   - schema validity
   - GenAI operation name
   - finish reason
   - errors

## Why This Matters

This moves Metis from post-hoc failure summaries toward real execution trace capture. For 9B-class models, this is critical because the harness must localize failures the model cannot explain reliably.

The design is intentionally local-first and dependency-free, but it aligns with OpenTelemetry GenAI concepts:

- model call events map toward chat spans;
- tool request/result events map toward execute-tool spans;
- parser and finalization repair events capture small-model self-correction boundaries;
- stable event ids give repair tasks future anchors.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\integration\test_parser_repair.py tests\integration\test_strict_output_block.py tests\integration\test_agent_loop_fake.py tests\unit\test_eval_runner.py tests\unit\test_timeline.py
```

Result:

```text
37 passed
```

## Remaining Gaps

1. Event severity:
   - classify events as info/warn/error/blocking.

2. Critical event selection:
   - automatically choose `critical_event_id` for each failed task.

3. Repair task event anchoring:
   - add `timeline_event_ids` and `critical_event_id` to repair tasks.

4. Source module mapping:
   - map event/failure type to likely Metis modules.

5. OTel export:
   - export local events into an OpenTelemetry-compatible JSON shape without requiring a collector.
