"""Weather tool plugin for Metis."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from metis.plugins.api import PluginContext
from metis.tools.spec import ToolContext, ToolSpec


def _get_weather_handler(args: dict[str, Any], context: ToolContext) -> str:
    city = str(args.get("city", "")).strip()
    if not city:
        return json.dumps({"error": "city is required"}, ensure_ascii=False)

    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return json.dumps({"error": f"Failed to fetch weather: {exc}"}, ensure_ascii=False)

    current = data.get("current_condition", [{}])[0]
    temp_c = current.get("temp_C", "?")
    temp_f = current.get("temp_F", "?")
    desc = current.get("weatherDesc", [{}])[0].get("value", "unknown")
    humidity = current.get("humidity", "?")

    return json.dumps(
        {
            "city": city,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "condition": desc,
            "humidity": humidity,
        },
        ensure_ascii=False,
    )


def register(context: PluginContext) -> None:
    context.register_tool(
        ToolSpec(
            name="get_weather",
            description="Get current weather conditions for a city.",
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'Beijing' or 'New York'",
                    },
                },
                "required": ["city"],
            },
            handler=_get_weather_handler,
            category="external_api",
            side_effect="read",
            permission_level="network",
        )
    )
