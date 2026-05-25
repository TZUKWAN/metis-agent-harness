import json

from metis.plugins.api import PluginContext
from metis.plugins.manager import PluginManager
from metis.tools.registry import ToolRegistry


def test_plugin_manager_loads_local_plugin(tmp_path):
    plugin_dir = tmp_path / "plugins" / "sample"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "sample", "name": "Sample", "entrypoint": "plugin.py"}),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(
        "from metis.tools.spec import ToolSpec\n"
        "def register(context):\n"
        "    context.register_tool(ToolSpec('sample_tool', 'Sample', {'type':'object'}, lambda args, ctx: {'ok': True}))\n",
        encoding="utf-8",
    )
    context = PluginContext(ToolRegistry())

    result = PluginManager(context).load_dir(plugin_dir)

    assert result.loaded is True
    assert context.tool_registry.list_tools() == ["sample_tool"]


def test_plugin_manager_captures_plugin_errors(tmp_path):
    plugin_dir = tmp_path / "plugins" / "bad"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text(json.dumps({"id": "bad"}), encoding="utf-8")
    (plugin_dir / "plugin.py").write_text("def register(context):\n    raise RuntimeError('boom')\n", encoding="utf-8")

    result = PluginManager(PluginContext(ToolRegistry())).load_dir(plugin_dir)

    assert result.loaded is False
    assert "boom" in result.error
