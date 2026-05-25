# Iteration 139 - Verify Repair Plan CLI

Date: 2026-05-25

## Problem

Iteration 138 made phase enforcement verify repair-plan attestation before trusting phase metadata.

That protected the enforcement path, but CI still lacked a standalone command for verifying an existing repair-plan artifact bundle. A release pipeline may want to verify a repair plan without regenerating it or requiring a phase immediately.

For a reusable harness, artifact verification should be independently runnable at each boundary.

## Implementation

Added:

```powershell
metis eval verify-repair-plan --plan-dir <directory>
```

The command calls:

```python
verify_repair_plan_attestation(plan_dir)
```

It returns:

- exit code `0` when attestation verifies;
- exit code `1` when verification fails.

Markdown output includes:

- plan directory;
- verified boolean;
- failure count;
- failure list.

JSON output is available through:

```powershell
metis eval verify-repair-plan --plan-dir <directory> --json
```

JSON fields:

- `plan_dir`
- `verified`
- `failure_count`
- `failures`

## Harness Impact

Repair-plan trust is now a standalone CI boundary.

The repair loop can now be decomposed into explicit checks:

1. build repair tasks;
2. build repair plan;
3. verify repair-plan attestation;
4. require executable phase;
5. execute repair work.

This makes the harness more composable. A future orchestrator, dashboard, or CI workflow can verify control-plane artifacts without coupling itself to plan generation or phase enforcement.

For 9B model workflows, this keeps the model downstream of deterministic trust checks.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_cli_eval.py -q
```

Result:

```text
44 passed
```

New coverage verifies:

1. successful verification prints Markdown and returns `0`;
2. failed verification prints JSON and returns `1`;
3. failure details are preserved in command output.

## Remaining Work

1. Add `verify-repair-plan` to documentation examples and CI recipe snippets.
2. Add attestation for targeted eval stubs and materialized suites.
3. Add signed attestation support.
4. Add repair execution command that requires verified plan artifacts before running.
