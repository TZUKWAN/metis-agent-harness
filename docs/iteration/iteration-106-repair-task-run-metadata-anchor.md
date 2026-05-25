# Iteration 106 - Repair Task Run Metadata Anchor

This iteration propagates failed timeline `run_metadata` into comparison diagnosis and repair tasks.

## Problem

Iteration 105 added run-level contract anchors to failed timelines. That made individual trace artifacts self-contained, but the repair pipeline still dropped the metadata:

1. comparison reason links carried timeline paths;
2. diagnosis extracted timeline event ids and schema repair hint events;
3. repair tasks inherited those event anchors;
4. repair tasks did not inherit run-level provenance and pre-run contract anchors.

That forced humans or automation to reopen timeline files to recover the run contract.

## Changes

1. `eval_run_comparison_diagnosis()` now reads each linked timeline's top-level `run_metadata`.
2. Diagnosis entries now include `run_metadata`, keyed by task id.
3. `build_repair_tasks_from_diagnosis()` copies `run_metadata` into repair tasks.
4. Diagnosis Markdown renders compact run metadata anchors:
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
   - `provenance_hash`
   - `task_contract_hash`
5. Test coverage verifies timeline -> diagnosis -> repair task propagation.

## Why This Matters

The Metis harness should convert failed traces into actionable repair work without requiring another round of manual artifact discovery. For small models, the repair payload must be dense and explicit:

1. which task failed;
2. which event likely failed;
3. what schema/tool hint was involved;
4. which run contract governed the failure.

This iteration adds the fourth point to repair tasks.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `43 passed`

## References Checked

- OpenTelemetry trace concepts emphasize propagating context across linked spans and operations.
- Agent trace debugging guidance emphasizes turning traces into structured diagnostic signals.
- AgentRx-style failure attribution focuses on identifying critical failure steps in trajectories, which Metis now ties to contract metadata.

## Next Gaps

1. Propagate repair task `run_metadata` into targeted eval stubs.
2. Preserve source repair task `run_metadata` in materialized eval suites.
3. Add `run-attestation.json` with digests for all major run artifacts.
4. Add OpenTelemetry-compatible JSON export for local timelines.
5. Add suite-scoped latest pointers for generic suites.
