# Metis Architecture

Metis is a domain-neutral agent harness composed of task intake, prompt assembly, provider normalization, tool dispatch, state, planning, context budgeting, artifacts, evidence, quality gates, recovery, security, loops, swarm orchestration, skills, plugins, reusable app surfaces, and adapters.

## Runtime Path

The target runtime path is:

```text
Input Surface -> TaskContractV1 -> PromptStack -> AgentRunRequest -> AgentLoop -> Tools/Evidence/Finalization
```

Current reusable app surfaces (`metis run`, `metis tui`, and `metis web`) build a `TaskContractV1` from the user request and assemble a hashable `PromptStack` containing base harness instructions, optional manifest prompts, the task contract, and the strict output contract for small-model profiles.

`AgentRunRequest` carries `task_contract_hash` and `prompt_stack_hash`. `AgentLoop` records both hashes in the `agent.start` trace event so a run can be audited against the contract and prompt stack used at intake time.

Reusable app surfaces also share runtime status construction. Web exposes this through `/api/status`; TUI prints the active runtime identity at startup. The status includes manifest values, provider capabilities, allowed tool permissions, registered tool names, and optional state database path. Web also exposes session summaries and session detail so messages, tool-call summaries, and evidence summaries can be inspected by app shells. When a state database is configured, Web can read persisted sessions from SQLite instead of relying only on in-memory sessions.

## Core Layers

- `planning`: structured task contracts and legacy step-scoped contract fragments.
- `prompts`: ordered, source-aware, hashable prompt stack assembly.
- `runtime`: agent loop, profiles, budgets, execution controller, strict output, finalization, and trace events.
- `state`: SQLite-backed state can persist run checkpoints for start/finalization phases when a state backend is attached.
- `state` checkpoint inspection is exposed through `metis checkpoint list` and `metis checkpoint latest` so persisted run progress can be audited from CLI/CI.
- `state` resume is exposed through `metis resume`, which restores persisted messages, appends a new user instruction, records `agent.resume`, and continues the loop in the same session.
- `app` surfaces can opt into the same SQLite state backend with `state_db_path`, `METIS_STATE_DB`, or `--state-db`.
- `providers`: model provider abstraction, OpenAI-compatible endpoint support, and capability metadata for native tool calling, JSON schema output, streaming, thinking, context limits, output limits, and retryable status codes.
- `tools`: registry, routing, dispatch, schema validation, guardrails, and result persistence.
- `tools` also expose permission levels and can block calls whose permission level is not allowed by the active runtime context.
- `evidence`: typed evidence extraction, ledger, matching, and resolution.
- `evidence` includes claim mapping for high-risk final claims such as tested, generated, uploaded, fixed, verified, reviewed, called API, deployed, merged, and released.
- `evals`: eval suites, validation, run comparison, release gates, repair plans, and attestation.
- `evals` release gates support `dev`, `candidate`, and `release` profiles so local development can be permissive while release validation stays strict.
- `evals` repair execution can preflight verified repair plans, record attempts, and optionally run declared no-shell safe commands with execution evidence.
- `app`: manifest-driven CLI/TUI/Web shells for downstream agents.
- `develop`: developer-facing customization workflow for creating downstream agent packages.
- `package_lifecycle`: package build and verify helpers for portable downstream agent directories.
- `plugins`: extension manifest and runtime registration boundary for tools, prompt fragments, quality gates, role templates, artifact validators, eval suites, evidence requirements, and uninstall scope.

## Provider Capabilities

Every provider can expose a `ProviderCapabilities` object. The OpenAI-compatible provider reports:

- `provider_type`: stable provider family identifier.
- `model`: active model name.
- `native_tool_calling`: whether Metis can send native tool schemas to the provider.
- `json_schema_output`: explicit structured output support when configured.
- `streaming`: whether this provider implementation currently streams responses.
- `thinking`: whether the active model/configuration is expected to support thinking parameters.
- `max_context_tokens` and `max_output_tokens`: configured limits when known.
- `retryable_status_codes`: HTTP status codes treated as retryable provider failures.

The CLI exposes this inventory through `metis provider capabilities`. This is intended to be consumed by eval setup, downstream package validation, and future app-shell diagnostics instead of relying on undocumented provider assumptions.

## Plugin Boundary

Plugins are loaded through an explicit manifest. The manifest declares identity, version, entrypoint, contributed tools, required permissions, eval suites, prompt fragments, evidence requirements, and relative uninstall paths. Metis validates this manifest before executing the plugin entrypoint so an invalid plugin cannot silently mutate the harness context.

The CLI exposes plugin inspection through:

```powershell
metis plugin inspect --path ./plugins/example --json
```

This makes plugin review and downstream package auditing possible without executing arbitrary plugin code.
