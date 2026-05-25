# Metis App Surfaces

Metis provides reusable user-facing shells so downstream agents do not need to build separate CLI, TUI, and Web UI layers from scratch.

## App Manifest

Create a manifest:

```powershell
metis app init --name "Acme Analyst" --output metis-agent.json
```

The manifest controls branding and defaults:

```json
{
  "name": "Acme Analyst",
  "subtitle": "Agent Harness",
  "description": "Acme Analyst powered by Metis Agent Harness",
  "version": "0.1.0",
  "workspace": ".",
  "model": "glm-4.7-flash",
  "base_url": "",
  "profile": "small",
  "icon_text": "A",
  "system_prompt_path": "prompts/acme-analyst-system.md",
  "developer_prompt_path": "prompts/acme-analyst-developer.md"
}
```

Environment overrides:

- `METIS_APP_MANIFEST`
- `METIS_APP_NAME`
- `METIS_APP_SUBTITLE`
- `METIS_APP_DESCRIPTION`
- `METIS_APP_VERSION`
- `METIS_APP_ICON`
- `METIS_WORKSPACE`
- `METIS_MODEL`
- `METIS_BASE_URL`
- `METIS_PROFILE`
- `METIS_SYSTEM_PROMPT_PATH`
- `METIS_DEVELOPER_PROMPT_PATH`

Prompt paths are optional. When present, the CLI, TUI, and Web runtime surfaces load them and prepend them as system messages before the user's task. Relative prompt paths are resolved from the manifest workspace.

## CLI

One-shot CLI task:

```powershell
metis run "Inspect this repository and summarize risks" --manifest metis-agent.json
```

## TUI

Reusable terminal UI:

```powershell
metis tui --manifest metis-agent.json
```

The TUI uses the same manifest and runtime loop as CLI and Web.

## Web UI

Reusable Web UI:

```powershell
metis web --manifest metis-agent.json --host 127.0.0.1 --port 8080
```

The Web UI is a Metis-specific app shell adapted from the Sophia-style chat interface:

- sidebar brand area;
- reusable session list;
- model/profile/workspace labels;
- WebSocket chat endpoint;
- HTTP chat fallback;
- manifest-driven app name, subtitle, description, icon, model, profile, and workspace.
- manifest-driven system and developer prompts.

Install optional UI dependencies when packaging Metis:

```powershell
pip install "metis-agent-harness[ui]"
```

## Downstream Agent Rebranding

A downstream agent should only need to:

1. provide `metis-agent.json`;
2. register its domain tools or adapters;
3. set model credentials through environment variables;
4. launch `metis run`, `metis tui`, or `metis web`.

The goal is that the UI shell remains Metis-owned while the downstream agent replaces branding, prompts, and tool/runtime configuration.
