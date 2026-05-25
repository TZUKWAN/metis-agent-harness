# Iteration 023 - Verified Real Eval and Report Metadata

Date: 2026-05-25

## Goal

The real small-model eval suite had strict tool and trajectory gates, but it still lacked a verified-final task. The reason was structural: tools could record evidence internally, but successful tool messages did not expose evidence IDs back to the model. A real model cannot cite an evidence ref it never sees.

This iteration fixes that harness gap and adds real-suite metadata.

## Runtime Change

File: `metis/runtime/loop.py`

When `EvidenceLedger` is attached:

1. `AgentLoop` records extracted tool evidence as before.
2. The generated evidence IDs are collected.
3. The IDs are attached to `ToolResult.metadata["evidence_refs"]`.
4. Successful tool messages with evidence are wrapped as JSON:

```json
{
  "result": { "...": "original tool result" },
  "evidence_refs": ["..."],
  "evidence_instruction": "Use these evidence_refs in the final JSON when making claims supported by this tool result."
}
```

The raw `ToolResult.content` remains unchanged. This preserves internal evidence extraction and state resolution while giving the model enough information to produce verified final output.

## Eval Report Metadata

File: `metis/evals/runner.py`

`EvalSuiteResult` now includes:

- `metadata`

Reports now write metadata to both:

- `eval-report.json`
- `eval-report.md`

`EvalRunner.run_suite()` accepts optional metadata.

## Real Suite Change

File: `metis/evals/real_model_suite.py`

Added:

- `real_small_model_eval_metadata()`

Metadata includes:

- suite name
- task count
- model
- base URL
- profile

Added task:

### `verified-test-evidence`

Purpose:

- Run `run_test`.
- Use tool-returned `evidence_refs` in final JSON.
- Require verified final.

Key gates:

- `required_evidence_sources=["test"]`
- `require_verified_final=True`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

## Tests

Added/updated tests:

1. `test_agent_loop_records_extracted_command_evidence`
   - verifies tool message contains real evidence refs.

2. `test_eval_suite_writes_metadata_to_reports`
   - verifies JSON and Markdown reports include metadata.

3. `test_real_small_model_eval_suite_declares_strict_default_gates`
   - verifies `verified-test-evidence` exists.
   - verifies it requires verified final and test evidence.

4. `test_real_small_model_eval_metadata_declares_model_profile_and_task_count`
   - verifies suite metadata.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_evidence_extraction.py tests\unit\test_eval_runner.py tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
29 passed, 2 skipped in focused tests
compileall passed
176 passed, 3 skipped in full test suite
```

## Remaining Risk

Verified final now has a viable information path, but the real suite still needs broader verified tasks:

1. verified command evidence;
2. verified file/write evidence;
3. verified read/write report evidence;
4. failed evidence-ref recovery;
5. report metadata persisted to a stable repository report path after real runs.
