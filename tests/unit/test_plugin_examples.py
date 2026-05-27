"""Tests verifying all official example plugins load correctly."""

from __future__ import annotations

from pathlib import Path

from metis.plugins.api import PluginContext
from metis.plugins.manager import PluginManager
from metis.tools.registry import ToolRegistry

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples" / "plugins"


def test_weather_tool_plugin_loads() -> None:
    registry = ToolRegistry()
    ctx = PluginContext(tool_registry=registry)
    mgr = PluginManager(ctx)
    result = mgr.load_dir(EXAMPLES_DIR / "weather-tool")
    assert result.loaded is True
    assert result.error == ""
    assert registry.get("get_weather") is not None


def test_custom_gate_plugin_loads() -> None:
    registry = ToolRegistry()
    ctx = PluginContext(tool_registry=registry)
    mgr = PluginManager(ctx)
    result = mgr.load_dir(EXAMPLES_DIR / "custom-gate")
    assert result.loaded is True
    assert result.error == ""
    assert "no_hardcoded_paths" in ctx.quality_gates


def test_prompt_fragment_plugin_loads() -> None:
    registry = ToolRegistry()
    ctx = PluginContext(tool_registry=registry)
    mgr = PluginManager(ctx)
    result = mgr.load_dir(EXAMPLES_DIR / "prompt-fragment")
    assert result.loaded is True
    assert result.error == ""
    assert len(ctx.prompt_fragments) == 1
    assert "Chinese" in ctx.prompt_fragments[0]
