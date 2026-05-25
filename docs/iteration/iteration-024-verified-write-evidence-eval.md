# Iteration 024 - Verified Write Evidence Eval

Date: 2026-05-25

## Goal

Iteration 023 made test evidence usable in verified-final tasks. The next gap was file delivery. Many real agent tasks produce files or reports, so a trustworthy harness must force the model to cite evidence for file creation or modification, not merely claim that the file was written.

This iteration adds verified `write_file` evidence to the real small-model eval suite.

## Runtime Foundation

No new runtime API was required. The previous evidence-ref feedback path now supports `write_file`:

1. `write_file` returns a path.
2. `ToolEvidenceExtractor` records `tool_output` evidence.
3. `EvidenceLedger` stores the evidence ID.
4. `AgentLoop` sends that evidence ID back to the model in the tool message.
5. The model can cite that ID in final `evidence_refs`.
6. `FinalizationGuard` and `EvidenceResolver` can resolve it against the successful tool call.

## Real Suite Change

File: `metis/evals/real_model_suite.py`

Added task:

### `verified-write-evidence`

Purpose:

- Use `write_file` to create `outputs/verified-write.md`.
- Require the final JSON to include evidence refs returned by `write_file`.
- Require verified final status.

Key gates:

- `required_tools=["write_file"]`
- `required_evidence_sources=["tool_output"]`
- `require_verified_final=True`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

## Tests

Updated:

- `tests/e2e/test_local_9b_eval.py`
  - verifies the real suite now includes `verified-write-evidence`;
  - verifies it requires `tool_output` evidence;
  - verifies it requires `path=outputs/verified-write.md`.

Added:

- `test_agent_loop_returns_write_file_evidence_refs_to_model`
  - runs a real `write_file` tool call through `AgentLoop`;
  - verifies `EvidenceLedger` records `tool_output` evidence;
  - verifies the tool message contains the evidence ID for the model.

## Verification

Commands run:

```powershell
python -m pytest -q tests\integration\test_agent_loop_evidence_extraction.py tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
python -m pytest -q
```

Results:

```text
4 passed, 2 skipped in focused tests
compileall passed
177 passed, 3 skipped in full test suite
```

## External References

OpenAI agent eval docs and LangChain agent eval docs both emphasize evaluating tool-call trajectories instead of only final outputs. TRAJECT-Bench similarly argues that final-answer-only grading misses tool selection, parameterization, and ordering issues. Verified write evidence extends that trajectory principle to file-producing tasks: the final answer is trusted only when grounded in a recorded tool result.

References:

- https://platform.openai.com/docs/guides/agent-evals
- https://docs.langchain.com/oss/python/langchain/evals
- https://arxiv.org/abs/2510.04550

## Remaining Risk

The real suite now covers verified test and write evidence, but it still needs:

1. verified read-then-write report evidence;
2. explicit evidence-ref repair tasks;
3. stable persisted real-run reports under `docs/evals/runs/`;
4. stronger artifact-level validation for file content, not only file write evidence.
