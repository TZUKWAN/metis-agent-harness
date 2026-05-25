# Iteration 051 - Trace Show CLI and Event IDs

## Goal

Iteration 050 created compact failed-task timeline artifacts. This iteration makes those artifacts directly inspectable from the Metis CLI and assigns stable event ids so future repair tasks can point to exact events.

## Implemented

1. Added timeline helper module:
   - `metis.telemetry.timeline`

2. Added timeline loading:
   - `load_timeline(path)`
   - validates file existence.
   - loads JSON.
   - normalizes missing event metadata.

3. Added timeline normalization:
   - `normalize_timeline(timeline)`
   - ensures every event has:
     - `index`
     - `event_type`
     - `event_id`

4. Added rendering helpers:
   - `timeline_to_markdown(timeline, include_payload=False)`
   - `timeline_to_json(timeline)`

5. Added CLI command:
   - `metis trace show --timeline <timeline.json>`
   - `metis trace show --timeline <timeline.json> --json`
   - `metis trace show --timeline <timeline.json> --include-payload`

6. Failed eval timelines now include stable event ids:
   - `<task-id>:000:task.start`
   - `<task-id>:001:tool.result`
   - `<task-id>:002:error`
   - `<task-id>:003:task.end`

7. Added tests:
   - timeline normalization;
   - markdown rendering;
   - JSON rendering;
   - CLI markdown output;
   - CLI JSON output;
   - failed eval timeline event id export.

## Why This Matters

The external agent observability direction is converging around structured spans and event timelines. OpenTelemetry GenAI semantic conventions emphasize visibility into model calls, tool invocations, token usage, prompts, completions, and tool results. Agent failure diagnosis research similarly focuses on locating the critical failed step inside an execution trajectory.

Metis should stay local-first while remaining compatible with that direction. A file-based timeline with stable event ids gives Metis:

1. a durable local incident artifact;
2. a CLI inspection path;
3. stable references for repair tasks;
4. a future bridge to OpenTelemetry-style spans;
5. better debugging for small-model failures.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_timeline.py tests\unit\test_cli_eval.py tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py
```

Result:

```text
76 passed
```

## Remaining Gaps

The timeline is now viewable, but it is still derived from final eval result data. Next iterations should enrich the event stream at runtime:

1. `model.request`
2. `model.response`
3. `parser.repair.request`
4. `parser.repair.result`
5. `tool.request`
6. `tool.policy_decision`
7. `tool.result`
8. `finalization.check`
9. `finalization.result`

After that, repair tasks should include:

- `timeline_event_ids`
- `critical_event_id`
- likely source module
- suggested targeted eval
- verification command
