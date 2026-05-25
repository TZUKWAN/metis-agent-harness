# Iteration 142 - Repair Eval Artifact Verification CLI

Date: 2026-05-25

## Problem

Iteration 141 added attestation for targeted eval stubs and materialized targeted eval suites.

The next gap was standalone verification. CI should be able to verify those generated repair eval artifacts without needing to run Python helpers directly.

## Implementation

Added two CLI commands:

```powershell
metis eval verify-eval-stubs --stubs-dir <directory>
metis eval verify-targeted-suite --suite-dir <directory>
```

Both commands also support `--json`.

`verify-eval-stubs` calls:

```python
verify_targeted_eval_stubs_attestation(stubs_dir)
```

`verify-targeted-suite` calls:

```python
verify_targeted_eval_suite_attestation(suite_dir)
```

Both commands return:

- exit code `0` when verification passes;
- exit code `1` when verification fails.

Markdown output includes:

- artifact label;
- directory;
- verified flag;
- failure count;
- failure list.

JSON output includes:

- `artifact`
- `stubs_dir` or `suite_dir`
- `verified`
- `failure_count`
- `failures`

## Harness Impact

The repair eval artifact trust chain is now operational from the CLI:

```text
repair-plan -> targeted eval stubs -> materialized targeted suite
```

Each boundary can be verified independently before CI or a future repair executor consumes it.

This protects 9B workflows because model calls remain downstream of deterministic artifact checks.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_cli_eval.py -q
```

Result:

```text
48 passed
```

New coverage verifies:

1. successful stubs verification prints Markdown and returns `0`;
2. failed stubs verification prints JSON and returns `1`;
3. successful suite verification prints Markdown and returns `0`;
4. failed suite verification prints JSON and returns `1`;
5. failure details are preserved in command output.

## Remaining Work

1. Add these verification commands to the CI recipe.
2. Enforce targeted suite attestation before running repair eval suites.
3. Add signed attestation support.
4. Add GitHub Actions and local PowerShell examples.
