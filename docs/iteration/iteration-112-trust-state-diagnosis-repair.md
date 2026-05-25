# Iteration 112 - Trust State in Diagnosis and Repair Tasks

This iteration propagates eval comparison trust state into diagnosis and repair artifacts.

## Problem

Iteration 111 added `baseline_untrusted` and `current_untrusted` to comparison output. That helped CI and dashboards.

The repair loop still consumed `diagnosis.json` and `repair-tasks.json`. If trust state stayed only in `comparison.json`, an automated repair agent had to reopen the full comparison or infer from text that an artifact bundle, not model behavior, was the problem.

## Changes

1. `eval_run_comparison_diagnosis()` now includes:
   - `baseline_untrusted`
   - `current_untrusted`
2. `attestation_untrusted` diagnosis entries now include `trust_state`.
3. `trust_state` contains:
   - `baseline_untrusted`
   - `current_untrusted`
   - `baseline_failures`
   - `current_failures`
4. `eval_run_diagnosis_to_markdown()` renders trust state.
5. `build_repair_tasks_from_diagnosis()` preserves `trust_state`.
6. `attestation_untrusted` repair tasks are classified as:
   - `priority: critical`
   - `owner_area: artifact-integrity-and-provenance`
7. Source localization for attestation trust failures points to:
   - `metis/evals/attestation.py`
   - `metis/evals/compare.py`
   - `metis/evals/gate.py`
   - `metis/evals/runner.py`
8. Suggested repair action tells the operator or agent to repair/regenerate the run artifact bundle, rerun attestation verification, then repeat comparison.

## Why This Matters

Metis should help small models do high-quality engineering by removing ambiguity from the task payload.

An artifact trust failure is not a prompt failure, schema repair failure, or planning failure. It is a release-blocking provenance problem. The repair artifact now says that directly.

The chain is now:

```text
comparison attestation failure
-> attestation_untrusted reason
-> diagnosis trust_state
-> critical artifact-integrity repair task
-> source modules and verification direction
```

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `46 passed`

## Remaining Gaps

1. Repair plan phases should treat artifact integrity as a precondition phase.
2. Targeted eval stubs should create artifact verification fixtures for `attestation_untrusted`, not model behavior evals.
3. Markdown reports should render subject counts and failed subject names.
4. Attestations still need signing support.
