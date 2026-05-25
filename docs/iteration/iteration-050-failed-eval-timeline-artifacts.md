# Iteration 050 - Failed Eval Timeline Artifacts

## Goal

Repair tasks need precise evidence. Before this iteration, failed eval artifacts contained metrics, errors, task specs, and tool result excerpts, but there was no dedicated timeline artifact for a failed task.

This iteration adds compact failed-task timelines. The intent is to make every failure easier to inspect, link, triage, and eventually replay.

## Implemented

1. Failed eval artifact export now writes timeline files for each failed task:
   - `<task>.timeline.json`
   - `<task>.timeline.md`

2. Failure index entries now include:
   - `timeline_path`
   - `timeline_markdown_path`

3. Failure artifact payloads now include:
   - `timeline_path`

4. Timeline JSON contains:
   - `task_id`
   - `success`
   - `status`
   - `event_count`
   - ordered `events`

5. Timeline events currently include:
   - `task.start`
   - `tool.result`
   - `error`
   - `task.end`

6. Tool result timeline events carry:
   - tool index
   - tool name
   - tool call id
   - status
   - failed flag
   - selected metadata
   - content preview
   - error preview

7. Comparison reason links now include timeline paths when the current run failure index has them:
   - task-level reasons
   - metric reasons
   - task spec reasons
   - cluster reasons

8. Diagnosis and repair task payloads now carry:
   - `timeline_paths`

9. Repair task markdown now renders:
   - `Timelines`

## Why This Matters

Modern agent debugging practice increasingly centers on trace-level review and span-level localization. A final answer can be wrong for many reasons: bad tool choice, bad arguments, policy block, failed command, ignored tool output, evidence mismatch, retry loop, or finalization failure.

For 9B-class models, this distinction is critical. The harness has to locate the failing boundary because the model often cannot reliably explain its own failure. Timeline artifacts make the failure boundary inspectable and machine-linkable.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_eval_runner.py tests\unit\test_eval_compare.py tests\unit\test_cli_eval.py
```

Result:

```text
71 passed
```

## Remaining Gaps

This is still a compact synthetic timeline derived from eval results. The next stronger version should:

1. attach model input/output events;
2. attach parser repair events;
3. attach tool call request events before tool result events;
4. attach policy decision events;
5. attach finalization gate decision events;
6. assign stable span ids;
7. allow repair tasks to point to a specific event index;
8. support `metis trace show <timeline-path>`;
9. support replay or partial rerun for deterministic failures.
