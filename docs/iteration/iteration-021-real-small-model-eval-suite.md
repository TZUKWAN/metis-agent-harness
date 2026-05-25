# Iteration 021 - Real Small-model Eval Suite

Date: 2026-05-25

## Goal

The previous iterations made Metis stronger at controlling and evaluating small-model failures, but most checks still used `FakeProvider`. A world-class harness cannot claim 9B readiness without a real-provider eval suite.

This iteration adds the first reusable real small-model eval suite. It is designed to be honest:

- no API key is committed;
- no fake model output is substituted;
- tests skip when endpoint configuration is absent;
- when endpoint configuration exists, the suite runs through the real `OpenAICompatibleProvider`.

## New Module

File: `metis/evals/real_model_suite.py`

Added:

- `real_model_env_configured()`
- `real_small_model_eval_tasks()`
- `build_real_small_model_eval_runner()`
- `run_real_small_model_eval_suite()`

The runner uses:

- `OpenAICompatibleProvider`
- `AgentLoop`
- built-in tools
- `small` model profile
- workspace-local SQLite state

## Eval Tasks

### 1. `strict-final-no-tools`

Purpose:

- Validate strict final JSON behavior without tools.

Default gates:

- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

### 2. `read-then-summarize`

Purpose:

- Require a real `read_file` tool call against `README.md`.
- Verify tool selection and argument discipline.

Default gates:

- required tool: `read_file`
- forbidden tools: `write_file`, `run_shell`, `run_command`, `run_test`
- required argument: `path=README.md`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

### 3. `safe-command`

Purpose:

- Require a safe `run_command` call.
- Forbid `run_shell`.

Default gates:

- required tool: `run_command`
- forbidden tool: `run_shell`
- required argument contains `python`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`
- `max_failure_shape_key_counts={"python pytest": 0}`

## Tests

File: `tests/e2e/test_local_9b_eval.py`

Added:

1. A non-network test that verifies the suite declares strict default gates.
2. A network test that runs the real suite only when all required environment variables are present:
   - `METIS_BASE_URL`
   - `METIS_API_KEY`
   - `METIS_MODEL`

When those variables are missing, the test skips instead of faking results.

## Documentation

Updated:

- `docs/evals/9b-eval-report.md`

The report now documents current suite tasks, strict gates, and latest local check result.

## Verification

Commands run:

```powershell
python -m pytest -q tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
1 passed, 2 skipped in local real-eval test file
compileall passed
174 passed, 3 skipped in full test suite
```

The skipped tests are network/real-endpoint tests that require explicit environment configuration.

## Remaining Risk

This is the first real suite, not the full 20-task benchmark. Next steps:

1. Expand from 3 tasks to at least 20 real-provider eval tasks.
2. Add verified-final tasks with real evidence refs.
3. Add schema repair tasks using real model behavior.
4. Add retry-budget obedience tasks.
5. Add real report generation into a stable output directory.
6. Add model/profile metadata to eval reports.
