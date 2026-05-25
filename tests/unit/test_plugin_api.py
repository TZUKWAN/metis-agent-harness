import json

from metis.adapters import cli
from metis.plugins.api import PluginContext
from metis.plugins.manager import PluginManager, load_plugin_manifest, validate_plugin_manifest
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


def test_plugin_context_registers_tool():
    context = PluginContext(ToolRegistry())
    context.register_tool(ToolSpec("hello", "Hello", {"type": "object"}, lambda args, ctx: "hi"))

    assert context.tool_registry.list_tools() == ["hello"]


def test_plugin_manifest_declares_extension_boundary(tmp_path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("def register(context):\n    pass\n", encoding="utf-8")
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "acme.plugin",
                "name": "Acme Plugin",
                "version": "1.2.3",
                "description": "Adds an Acme tool.",
                "tools": ["acme_lookup"],
                "required_permissions": ["read_only"],
                "eval_suites": ["evals/acme.json"],
                "prompt_fragments": ["prompts/acme.md"],
                "evidence_requirements": ["tool_result"],
                "uninstall_paths": ["prompts/acme.md"],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_plugin_manifest(plugin_dir)

    assert manifest.id == "acme.plugin"
    assert manifest.tools == ("acme_lookup",)
    assert manifest.required_permissions == ("read_only",)
    assert manifest.eval_suites == ("evals/acme.json",)
    assert validate_plugin_manifest(manifest, plugin_dir) == ()
    assert manifest.to_dict()["tools"] == ["acme_lookup"]


def test_plugin_manifest_accepts_utf8_bom(tmp_path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("def register(context):\n    pass\n", encoding="utf-8")
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "bom.plugin", "name": "BOM Plugin"}),
        encoding="utf-8-sig",
    )

    manifest = load_plugin_manifest(plugin_dir)

    assert manifest.id == "bom.plugin"


def test_plugin_manager_rejects_invalid_manifest_without_executing(tmp_path):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "bad.plugin",
                "name": "Bad Plugin",
                "entrypoint": "missing.py",
                "uninstall_paths": ["../outside.txt"],
            }
        ),
        encoding="utf-8",
    )
    manager = PluginManager(PluginContext(ToolRegistry()))

    result = manager.load_dir(plugin_dir)

    assert result.loaded is False
    assert "entrypoint does not exist" in result.error
    assert "uninstall path must be relative" in result.error


def test_cli_plugin_inspect_prints_json(tmp_path, capsys):
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("def register(context):\n    pass\n", encoding="utf-8")
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "acme.plugin", "name": "Acme Plugin", "tools": ["acme_lookup"]}),
        encoding="utf-8",
    )

    exit_code = cli.main(["plugin", "inspect", "--path", str(plugin_dir), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["manifest"]["tools"] == ["acme_lookup"]
