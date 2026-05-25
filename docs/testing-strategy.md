# Testing Strategy

Core behavior is covered by unit, integration, e2e, and optional network tests. Real model tests use the `network` marker and skip when credentials are absent; they must not fake endpoint success.

Historical local hardening baseline after the third optimization round:

- Full suite: `100 passed, 2 skipped`
- Compile check: `python -m compileall -q metis`
- Network smoke: run with `METIS_BASE_URL`, `METIS_API_KEY`, and `METIS_MODEL`

Current architecture-hardening checks should include:

- `python -m compileall -q metis`
- `python -m pytest tests/unit/test_task_contract.py tests/unit/test_prompt_assembler.py tests/unit/test_app_runtime.py tests/unit/test_develop_workflow.py tests/unit/test_cli_eval.py tests/integration/test_agent_loop_contract_trace.py -q`
- `python -m pytest -q`

Task-contract and prompt-stack changes must prove:

- `TaskContractV1` hash stability.
- Prompt layer ordering and disabled-layer exclusion.
- Manifest prompts and task contracts entering runtime messages.
- `AgentLoop` trace events recording `task_contract_hash` and `prompt_stack_hash`.
