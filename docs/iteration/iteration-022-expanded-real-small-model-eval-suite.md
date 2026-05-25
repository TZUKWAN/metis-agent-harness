# Iteration 022 - Expanded Real Small-model Eval Suite

Date: 2026-05-25

## Goal

Iteration 021 introduced the first real small-model eval suite with three tasks. That was enough to prove the entry point, but not enough to cover the harness behaviors that matter for 9B models.

This iteration expands the real-provider suite from 3 tasks to 9 tasks. The suite is still honest:

- no API key is committed;
- real model execution is skipped when endpoint configuration is missing;
- task specification tests always run locally;
- no fake model output is substituted for real endpoint results.

## Updated Suite

File: `metis/evals/real_model_suite.py`

Current tasks:

1. `strict-final-no-tools`
   - Strict final JSON without tools.

2. `read-then-summarize`
   - Requires `read_file`.
   - Requires `path=README.md`.

3. `safe-command`
   - Requires `run_command`.
   - Forbids `run_shell`.
   - Blocks repeated `python pytest` failure shape.

4. `write-report-file`
   - Requires `write_file`.
   - Requires `path=outputs/real-model-report.md`.
   - Forbids read and command tools.

5. `read-then-write-summary`
   - Requires `read_file` before `write_file`.
   - Requires `README.md` input and `outputs/readme-summary.md` output.
   - Forbids command tools.

6. `forbidden-shell-readme`
   - Requires README summarization using only `read_file`.
   - Forbids shell, command, test, and write tools.

7. `schema-repair-write-file`
   - Intentionally asks for one malformed `write_file` call.
   - Requires recovery through corrected `path=outputs/schema-repair.md`.
   - Requires `min_schema_repair_successes=1`.

8. `command-schema-repair`
   - Intentionally asks for malformed `run_command` timeout.
   - Requires recovery with integer timeout.
   - Requires `min_schema_repair_successes=1`.

9. `safe-test-command`
   - Requires `run_test`.
   - Requires a pytest command.
   - Forbids `run_shell`.

## Gate Pattern

Most tasks use strict zero-defect gates:

- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

Repair tasks intentionally allow one recoverable schema failure and require successful repair:

- `min_schema_repair_successes=1`
- `max_schema_repair_failures=0`
- `allow_recovered_schema_failures=True`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

## Runner Improvement

The real-model runner now wires an `EvidenceLedger` into `AgentLoop` and `EvalRunner`, preparing the suite for verified-final tasks in the next iteration.

## Tests

File: `tests/e2e/test_local_9b_eval.py`

Updated the suite specification test:

- validates all 9 task IDs;
- verifies strict default gates for non-repair tasks;
- verifies repair tasks require schema repair success;
- verifies `read-then-write-summary` requires tool order.

Network execution remains skipped unless all required environment variables are configured:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

## Documentation

Updated:

- `docs/evals/9b-eval-report.md`

The report now lists all 9 tasks and their core gates.

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

## External References

LangChain's agent eval documentation emphasizes trajectory evaluation over tool calls and messages. OpenAI eval guidance treats reusable evals as a way to catch behavior regressions. Metis now applies that idea directly to small-model harness behaviors: tool choice, argument correctness, schema repair, retry obedience, and safe tool routing.

References:

- https://docs.langchain.com/oss/python/langchain/evals
- https://platform.openai.com/docs/guides/evals

## Remaining Risk

The suite still does not reach the target 20 real-provider tasks. Next work:

1. Add verified-final/evidence-ref tasks.
2. Add retry-budget obedience tasks.
3. Add forbidden-tool adversarial tasks.
4. Add context compression tasks.
5. Add report quality gate tasks.
6. Persist model/base_url/profile metadata in eval reports.
