# Metis Agent Harness

Metis is a domain-neutral agent harness runtime. It is designed to make agents more reliable by externalizing task state, controlling tool use, preserving evidence, validating artifacts, and supporting small-model execution.

This repository is currently in the Sprint 1 runtime-kernel build phase.

## Current Scope

- Hook/event bus
- Tool registry and dispatcher
- Provider abstraction
- Tool-call parsers
- Minimal multi-turn agent loop
- Fake provider tests
- Optional OpenAI-compatible API smoke test through environment variables

## API Configuration

Do not hardcode API keys in source files. For real endpoint tests, set:

```powershell
$env:METIS_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
$env:METIS_API_KEY="<your key>"
$env:METIS_MODEL="glm-4.7-flash"
```

Then run:

```powershell
python -m pytest -q -m network
```

## Test

```powershell
python -m pytest -q
```

## Reusable App Surfaces

Metis includes a manifest-driven CLI/TUI/Web shell for downstream agents.

```powershell
metis app init --name "Acme Analyst" --output metis-agent.json
metis run "Summarize this workspace" --manifest metis-agent.json
metis run "Summarize this workspace" --manifest metis-agent.json --state-db .metis/state.db --session-id demo
metis tui --manifest metis-agent.json --state-db .metis/state.db
metis web --manifest metis-agent.json --state-db .metis/state.db --port 8080
```

The manifest controls app name, subtitle, description, icon, workspace, model, base URL, profile, and optional system/developer prompt paths. See `docs/app-surfaces.md`.

The Web UI also exposes runtime status at `/api/status`, including manifest values, provider capabilities, allowed tool permissions, and registered tools. When `state_db_path`, `METIS_STATE_DB`, or `--state-db` is configured, app surfaces persist session messages/checkpoints and Web can read persisted sessions after restart.

Developer workbench for creating a new scenario-specific agent:

```powershell
metis develop --request "Build a grant writing agent" --name "Grant Builder"
```

`metis develop` is separate from runtime user surfaces. It is the developer entry for natural-language customization of Metis into a downstream agent. It writes analysis, adaptation plan, implementation contract, task breakdown, and verification checklist first; approved branding, manifest prompt paths, prompts, Claude Code commands, Codex commands, run scripts, and task files are written only after approval. See `docs/developer-workbench.md`.

## Package Lifecycle

Portable downstream agent directories can be built and verified:

```powershell
metis package build --source ./metis-development --output ./dist/my-agent
metis package verify --path ./dist/my-agent --profile dev
metis package install --path ./dist/my-agent --install-dir ./agents/my-agent
metis package export --path ./dist/my-agent --output ./dist/my-agent.zip
```

`candidate` and `release` verification profiles require at least one eval suite under `evals/`.

## Provider Capability Inspection

```powershell
metis provider capabilities --model glm-4.7-flash --json
```

This prints the active provider capability metadata, including native tool calling, JSON schema support, thinking support, context/output limits, and retryable provider status codes. Limit values can be supplied through `METIS_PROVIDER_MAX_CONTEXT_TOKENS` and `METIS_PROVIDER_MAX_OUTPUT_TOKENS` when the provider does not publish them automatically.

## Plugin Manifest Inspection

```powershell
metis plugin inspect --path ./plugins/example --json
```

Plugin manifests declare contributed tools, required permissions, prompt fragments, eval suites, evidence requirements, and uninstall paths. Inspection validates manifest boundaries before plugin code is loaded.

## Checkpoint Inspection

```powershell
metis checkpoint list --state-db .metis/state.db --session-id <session-id> --json
metis checkpoint latest --state-db .metis/state.db --session-id <session-id> --json
metis resume --state-db .metis/state.db --session-id <session-id> --message "Continue from the last checkpoint"
```

These commands expose persisted run checkpoints for audit and CI diagnostics. `metis resume` restores persisted messages for a session, appends a new user instruction, records an `agent.resume` checkpoint, and continues the agent loop without duplicating old messages in state.

## Repair Execution

```powershell
metis eval repair-execute --plan-dir ./repair-plan --phase phase-1-stop-release-blockers --output-dir ./repair-execute --execute-safe-commands
```

When a verified repair plan declares `execution_commands` or `verification_commands` on the selected phase/tasks, `--execute-safe-commands` runs them with `shell=False` and writes `repair-execution-results.json/md` plus an updated repair attempt/plan.
