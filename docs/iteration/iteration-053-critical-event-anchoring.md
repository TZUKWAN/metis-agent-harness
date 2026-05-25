# Iteration 053 - Critical Event Anchoring

## Goal

Repair tasks already carry timeline paths, but a path still forces a human or automation layer to inspect the timeline again. This iteration adds deterministic critical event selection and event-id anchoring so repair tasks can point directly at likely failure boundaries.

## Implemented

1. Added timeline event id helpers:
   - `timeline_event_ids(timeline)`
   - `critical_event_id(timeline)`
   - `select_critical_event(timeline)`

2. Critical event selection currently prioritizes:
   - failed finalization events;
   - failed tool result events;
   - failed parser/finalization repair events;
   - error events;
   - final event fallback.

3. Repair task generation now reads timeline files when available and adds:
   - `timeline_event_ids`
   - `critical_event_ids`

4. Repair task markdown now renders:
   - `Critical events`

5. Tests added or updated:
   - timeline event id extraction;
   - critical event selection for failed tool events;
   - critical event selection for finalization failures;
   - repair task linkage to timeline event ids and critical event ids.

## Why This Matters

This closes another part of the eval-to-repair loop:

1. eval finds a failure;
2. comparison identifies regression reasons;
3. diagnosis extracts action entries;
4. repair task links artifacts and timelines;
5. repair task now also points to likely critical events.

For small models, event anchoring is important because the model should not be asked to reread a long trace and infer the root boundary from scratch. The harness should narrow the failure to a deterministic candidate event before any model-assisted repair.

## Validation

Targeted validation:

```powershell
python -m pytest -q tests\unit\test_timeline.py tests\unit\test_eval_compare.py
```

Result:

```text
29 passed
```

## Remaining Gaps

1. Critical event selection is rule-based. It should later incorporate cluster reason, metric deltas, and task constraints.

2. Repair plans should surface critical event ids at owner-area and phase level.

3. Source-module mapping should use event type and failure metadata.

4. OTel-compatible export should map critical events to span ids.
