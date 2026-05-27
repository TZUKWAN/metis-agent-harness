# Metis Plugin Quickstart

Build and verify your first Metis plugin in under 5 minutes.

---

## Step 1: Scaffold a Plugin

Use the CLI to generate a plugin template:

```bash
metis plugin init --name "My Weather Tool" --id "my-weather" --type tool --output ./plugins
```

This creates:

```
plugins/my-weather/
  manifest.json
  plugin.py
  README.md
```

---

## Step 2: Implement Your Tool

Edit `plugins/my-weather/plugin.py`:

```python
"""My weather tool plugin."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from metis.plugins.api import PluginContext
from metis.tools.spec import ToolContext, ToolSpec


def _get_weather(args: dict[str, Any], context: ToolContext) -> str:
    city = args.get("city", "Beijing")
    url = f"https://wttr.in/{city}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    current = data["current_condition"][0]
    return f"{city}: {current['temp_C']}C, {current['weatherDesc'][0]['value']}"


def register(context: PluginContext) -> None:
    context.register_tool(ToolSpec(
        name="get_weather",
        description="Get current weather for a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
        handler=_get_weather,
        category="external_api",
        permission_level="network",
    ))
```

---

## Step 3: Inspect the Plugin

```bash
metis plugin inspect --path ./plugins/my-weather
```

Expected output:

```
Plugin: my-weather (My Weather Tool)
Version: 0.1.0
Valid: True
Tools: get_weather
Required permissions: network
```

---

## Step 4: Load It in Code

```python
from metis.plugins.manager import PluginManager
from metis.plugins.api import PluginContext
from metis.tools.registry import ToolRegistry

registry = ToolRegistry()
ctx = PluginContext(tool_registry=registry)
mgr = PluginManager(ctx)

result = mgr.load_dir("./plugins/my-weather")
assert result.loaded

# The tool is now available in the registry
spec = registry.get("get_weather")
print(spec.description)
```

---

## Next Steps

- Read the full [Plugin Development Guide](./plugin-development.md)
- Explore official examples in `examples/plugins/`
- Register quality gates for eval suites
- Inject prompt fragments to customize agent behavior
