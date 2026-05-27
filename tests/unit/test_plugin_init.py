"""Tests for `metis plugin init` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from metis.adapters.cli import _plugin_init


class FakeArgs:
    def __init__(self, *, name: str, id: str, output: str, type: str) -> None:
        self.name = name
        self.id = id
        self.output = output
        self.type = type


def test_plugin_init_empty(tmp_path: Path) -> None:
    args = FakeArgs(name="Empty Plugin", id="empty-test", output=str(tmp_path), type="empty")
    assert _plugin_init(args) == 0

    plugin_dir = tmp_path / "empty-test"
    assert (plugin_dir / "manifest.json").exists()
    assert (plugin_dir / "plugin.py").exists()
    assert (plugin_dir / "README.md").exists()

    manifest = json.loads((plugin_dir / "manifest.json").read_text())
    assert manifest["id"] == "empty-test"
    assert manifest["name"] == "Empty Plugin"
    assert manifest["entrypoint"] == "plugin.py"

    plugin_code = (plugin_dir / "plugin.py").read_text()
    assert "def register(context: PluginContext)" in plugin_code


def test_plugin_init_tool(tmp_path: Path) -> None:
    args = FakeArgs(name="Tool Plugin", id="tool-test", output=str(tmp_path), type="tool")
    assert _plugin_init(args) == 0

    plugin_dir = tmp_path / "tool-test"
    manifest = json.loads((plugin_dir / "manifest.json").read_text())
    assert manifest["tools"] == ["my_tool"]
    assert manifest["required_permissions"] == ["read_only"]

    plugin_code = (plugin_dir / "plugin.py").read_text()
    assert "ToolSpec" in plugin_code
    assert "_my_tool_handler" in plugin_code


def test_plugin_init_gate(tmp_path: Path) -> None:
    args = FakeArgs(name="Gate Plugin", id="gate-test", output=str(tmp_path), type="gate")
    assert _plugin_init(args) == 0

    plugin_dir = tmp_path / "gate-test"
    manifest = json.loads((plugin_dir / "manifest.json").read_text())
    assert manifest["eval_suites"] == ["my_gate"]

    plugin_code = (plugin_dir / "plugin.py").read_text()
    assert "GateSpec" in plugin_code
    assert "_my_gate_handler" in plugin_code


def test_plugin_init_prompt(tmp_path: Path) -> None:
    args = FakeArgs(name="Prompt Plugin", id="prompt-test", output=str(tmp_path), type="prompt")
    assert _plugin_init(args) == 0

    plugin_dir = tmp_path / "prompt-test"
    manifest = json.loads((plugin_dir / "manifest.json").read_text())
    assert manifest["prompt_fragments"] == ["my_prompt_fragment"]

    plugin_code = (plugin_dir / "plugin.py").read_text()
    assert "register_prompt_fragment" in plugin_code
