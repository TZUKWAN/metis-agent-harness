# Metis Developer Workbench

`metis develop` is a developer-facing entry point for building a scenario-specific agent on top of Metis through natural-language customization.

It is not a runtime chat surface for end users. It is a development workbench: the developer describes the agent they want, Metis analyzes how the harness should be adapted, writes a plan, waits for approval, and then produces a runnable downstream agent package.

It is separate from runtime user surfaces:

- `metis run`
- `metis tui`
- `metis web`

## Workflow

The development workflow is intentionally staged:

1. User describes the desired agent.
2. Metis writes a developer analysis report.
3. Metis writes an adaptation plan.
4. Metis writes an implementation contract and verification checklist.
5. Metis asks for approval before applying adaptation artifacts.
6. After approval, Metis writes branding, manifest, prompts, slash commands, run scripts, and a fine-grained task file.
7. The generated `metis-agent.json` can be used directly by reusable runtime surfaces:

```powershell
metis run --manifest metis-agent.json "Describe your task here"
metis tui --manifest metis-agent.json
metis web --manifest metis-agent.json
```

## Command

Interactive:

```powershell
metis develop
```

Non-interactive proposal only:

```powershell
metis develop `
  --request "Build a grant writing agent for nonprofit proposals" `
  --output-dir ./metis-development
```

If `--name` is omitted, Metis attempts to infer the downstream agent name from the natural-language request. For reliable branding, pass `--name`.

Approved artifact generation:

```powershell
metis develop `
  --request "Build a grant writing agent for nonprofit proposals" `
  --name "Grant Builder" `
  --output-dir ./metis-development `
  --approve
```

## Proposal Artifacts

These are always written:

- `analysis-report.json`
- `analysis-report.md`
- `adaptation-plan.json`
- `adaptation-plan.md`
- `task-breakdown.json`
- `task-breakdown.md`
- `implementation-contract.json`
- `implementation-contract.md`
- `verification-checklist.json`
- `verification-checklist.md`

## Approved Artifacts

These are written only after approval:

- `metis-agent.json`
- `prompts/<agent>-system.md`
- `prompts/<agent>-developer.md`
- `.claude/commands/<agent>.md`
- `.codex/commands/<agent>.md`
- `metis-dev-tasks.json`
- `README.md`
- `branding.json`
- `developer-workflow.md`
- `scripts/run-cli.ps1`
- `scripts/run-tui.ps1`
- `scripts/run-web.ps1`

The approved manifest includes:

- `name`
- `subtitle`
- `description`
- `workspace`
- `model`
- `profile`
- `icon_text`
- `system_prompt_path`
- `developer_prompt_path`

The reusable CLI, TUI, and Web runtime surfaces load the manifest prompt paths and prepend those prompts before the user's task. This makes the generated package more than documentation: it changes the runtime behavior while preserving the Metis harness architecture.

## Architecture Rule

The default strategy is:

```text
prompt-first, manifest-driven, architecture-preserving
```

That means the developer workflow should adapt:

- system prompts;
- developer prompts;
- manifest branding;
- tool registration;
- eval contracts;
- slash commands;
- task orchestration.

Core runtime architecture changes should be treated as exceptional and should be justified in the adaptation plan before implementation.

## Quality Standard

The generated downstream package must satisfy these conditions before it should be considered usable:

- The developer requirement appears in the analysis, plan, prompts, and package README.
- The manifest is the single source of truth for runtime branding and prompt paths.
- The generated prompts preserve evidence-backed delivery, approval gates, small-task decomposition, and truthful status reporting.
- Claude Code and Codex commands use the same analysis, approval, task decomposition, implementation, and verification workflow.
- The task file is fine-grained enough for weaker models and every task contains a verification instruction.
- The generated package can be launched through `metis run`, `metis tui`, and `metis web` with the generated manifest.

## Task Decomposition

The fine-grained task logic lives in `metis.swarm.decomposer.decompose_development_plan()`. This keeps the developer workflow aligned with Metis orchestration instead of hiding task splitting inside the CLI.
