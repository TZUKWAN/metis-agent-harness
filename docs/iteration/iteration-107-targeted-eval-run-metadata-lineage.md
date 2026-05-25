# Iteration 107 - Targeted Eval Run Metadata Lineage

This iteration preserves repair task `run_metadata` in targeted eval stubs and materialized targeted suites.

## Problem

Iteration 106 moved failed timeline run metadata into repair tasks. The next conversion step still dropped it:

1. repair task carried original failure run metadata;
2. targeted eval stub kept reason, cluster, critical events, hint events, and source modules;
3. materialized suite kept repair metadata;
4. neither stub nor suite preserved the source run contract anchor.

That meant generated regression samples could lose their provenance once they became executable eval tasks.

## Changes

1. `_eval_stub_for_repair_task()` now copies `run_metadata` from repair task to stub.
2. `eval_stubs_to_markdown()` renders compact run metadata anchors.
3. `materialize_eval_suite_from_stubs()` copies stub `run_metadata` into each task wrapper.
4. `eval_suite_to_markdown()` renders materialized task run metadata anchors.
5. Tests prove:
   - repair task -> stub preserves `run_metadata`;
   - stub -> materialized suite preserves `run_metadata`;
   - Markdown reports show `pre_run_contract_sha256`.

## Why This Matters

Metis is building a repair/eval flywheel. The chain should be auditable:

1. a real run fails;
2. failed timeline records run contract identity;
3. diagnosis records the run contract;
4. repair task records the run contract;
5. targeted eval stub records the run contract;
6. materialized regression suite records the run contract.

This iteration closes steps 5 and 6.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `43 passed`

## References Checked

- Trace-to-regression workflows emphasize keeping failure provenance when turning traces into tests.
- Agent evaluation guidance treats generated regression examples as evidence artifacts, not anonymous samples.

## Next Gaps

1. Add `run-attestation.json` for major eval artifacts and generated repair/eval artifacts.
2. Add source run metadata schema validation to materialized suite validation.
3. Add OpenTelemetry-compatible JSON export for local timelines.
4. Split compare trust status into baseline/current trust categories.
5. Add suite-scoped latest pointers for generic eval suites.
