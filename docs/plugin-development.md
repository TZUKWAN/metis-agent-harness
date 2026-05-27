# Metis Plugin Development Guide

This document covers the complete lifecycle of a Metis plugin, from creation to distribution.

## Table of Contents

1. [What is a Metis Plugin?](#what-is-a-metis-plugin)
2. [Plugin Structure](#plugin-structure)
3. [Manifest Fields](#manifest-fields)
4. [The `register` Function](#the-register-function)
5. [PluginContext API](#plugincontext-api)
6. [Plugin Types](#plugin-types)
7. [Debugging Tips](#debugging-tips)
8. [Packaging and Distribution](#packaging-and-distribution)

---

## What is a Metis Plugin?

A Metis plugin is a Python package that extends the Metis Agent Harness at runtime. Plugins can:

- Register new tools (e.g., `get_weather`)
- Register quality gates for eval suites
- Inject prompt fragments into the agent's context
- Register custom provider types
- Register role templates for swarm orchestration

Plugins are loaded dynamically via `PluginManager.load_dir()`.

---

## Plugin Structure

Every plugin is a directory containing at least two files:

```
my-plugin/
  manifest.json   # Plugin metadata
  plugin.py       # Entrypoint with register() function
  README.md       # Documentation (recommended)
```

### manifest.json

```json
{
  "id": "my-plugin",
  "name": "My Plugin",
  "version": "0.1.0",
  "entrypoint": "plugin.py",
  "description": "What this plugin does",
  "tools": ["my_tool"],
  "required_permissions": ["read_only"],
  "eval_suites": ["my_gate"],
  "prompt_fragments": ["my_fragment"]
}
```

### plugin.py

```python
"""My plugin entrypoint."""

from __future__ import annotations

from metis.plugins.api import PluginContext


def register(context: PluginContext) -> None:
    # Register tools, gates, fragments, etc.
    pass
```

---

## Manifest Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | Yes | string | Unique plugin identifier (kebab-case) |
| `name` | Yes | string | Human-readable plugin name |
| `version` | No | string | SemVer version, default `"0.1.0"` |
| `entrypoint` | No | string | Python file to execute, default `"plugin.py"` |
| `description` | No | string | Brief description of the plugin |
| `tools` | No | string[] | Tool names registered by this plugin |
| `required_permissions` | No | string[] | Permission levels required |
| `eval_suites` | No | string[] | Quality gate names provided |
| `prompt_fragments` | No | string[] | Prompt fragment identifiers |
| `evidence_requirements` | No | string[] | Evidence types produced |
| `uninstall_paths` | No | string[] | Files to remove on uninstall |

---

## The `register` Function

The `register` function is the single entrypoint for your plugin. It receives a `PluginContext` instance and uses it to register extensions.

```python
def register(context: PluginContext) -> None:
    context.register_tool(...)
    context.register_quality_gate(...)
    context.register_prompt_fragment(...)
```

The function is called once when the plugin is loaded. All registration must happen synchronously inside this function.

---

## PluginContext API

### `register_tool(spec: ToolSpec)`

Register a new tool available to agents.

```python
from metis.tools.spec import ToolSpec, ToolContext
from typing import Any

def handler(args: dict[str, Any], context: ToolContext) -> str:
    name = args.get("name", "world")
    return f"Hello, {name}!"

context.register_tool(ToolSpec(
    name="greet",
    description="Greet someone by name.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name to greet"},
        },
        "required": ["name"],
    },
    handler=handler,
    category="general",
    side_effect="read",
    permission_level="read_only",
))
```

**ToolSpec fields:**

- `name`: Tool identifier (must be unique)
- `description`: Description for the LLM
- `parameters`: JSON Schema for arguments
- `handler`: Callable `(args, ToolContext) -> Any`
- `category`: Tool category string
- `side_effect`: `"read"`, `"write"`, or `"mutate"`
- `permission_level`: `"read_only"`, `"workspace_write"`, `"shell_safe"`, `"shell_dangerous"`, `"network"`, etc.
- `requires_permission`: Whether explicit user approval is needed

### `register_quality_gate(spec: GateSpec)`

Register a quality gate for eval suites.

```python
from metis.quality.gates import GateSpec, GateResult
from typing import Any

def handler(context: dict[str, Any]) -> GateResult:
    return GateResult("my_gate", True, "Passed", {})

context.register_quality_gate(GateSpec(
    name="my_gate",
    description="My custom gate",
    handler=handler,
    failure_policy="fail",  # or "warn"
))
```

**GateResult fields:**

- `name`: Gate identifier
- `passed`: Boolean result
- `message`: Human-readable result message
- `metadata`: Optional dict for diagnostics

### `register_prompt_fragment(text: str)`

Inject text into the agent's prompt stack.

```python
context.register_prompt_fragment(
    "Always format dates as YYYY-MM-DD."
)
```

### `register_provider_type(name: str, cls: type)`

Register a custom model provider class.

```python
context.register_provider_type("my_provider", MyProviderClass)
```

### `register_role_template(role: RoleTemplate)`

Register a swarm role template.

```python
from metis.swarm.roles import RoleTemplate

context.register_role_template(RoleTemplate(
    role_id="reviewer",
    name="Code Reviewer",
    system_prompt="You are a meticulous code reviewer...",
))
```

---

## Plugin Types

### Tool Plugin

Extends agent capabilities with new tools. See `examples/plugins/weather-tool/`.

### Quality Gate Plugin

Adds eval suite gates. See `examples/plugins/custom-gate/`.

### Prompt Fragment Plugin

Modifies agent behavior via prompt injection. See `examples/plugins/prompt-fragment/`.

### Composite Plugin

A single plugin can register multiple extension types:

```python
def register(context: PluginContext) -> None:
    context.register_tool(...)
    context.register_quality_gate(...)
    context.register_prompt_fragment(...)
```

---

## Debugging Tips

### Inspect a Plugin

```bash
metis plugin inspect --path ./my-plugin
```

### Verify Loading

```python
from metis.plugins.manager import PluginManager
from metis.plugins.api import PluginContext
from metis.tools.registry import ToolRegistry

registry = ToolRegistry()
ctx = PluginContext(tool_registry=registry)
mgr = PluginManager(ctx)
result = mgr.load_dir("./my-plugin")
print(result.loaded, result.error)
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `entrypoint does not exist` | `plugin.py` missing | Ensure entrypoint file exists |
| `plugin id is required` | Empty `id` in manifest | Fill in a unique identifier |
| `register` not found | Missing `register` function | Define `def register(context): ...` |
| Tool name collision | Tool already registered | Use unique tool names or set `overwrite=True` |

---

## Packaging and Distribution

### Directory Layout

```
my-plugin/
  manifest.json
  plugin.py
  README.md
  requirements.txt    # Optional: pip dependencies
```

### Distribution

Plugins are distributed as plain directories or zip archives. Users place them in their Metis plugins directory and load them via `PluginManager`.

### Versioning

Use semantic versioning in `manifest.json`. Breaking changes should bump the major version.
