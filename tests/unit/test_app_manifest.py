import json

from metis.app.manifest import load_app_manifest, write_default_app_manifest


def test_load_app_manifest_uses_json_and_environment_overrides(monkeypatch, tmp_path):
    path = tmp_path / "metis-agent.json"
    path.write_text(
        json.dumps(
            {
                "name": "Custom Agent",
                "subtitle": "Custom Harness",
                "description": "Runs custom work",
                "workspace": "workspace-a",
                "model": "model-a",
                "profile": "small",
                "allowed_tool_permissions": "read_only",
                "state_db_path": ".metis/state.db",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("METIS_APP_NAME", "Env Agent")
    monkeypatch.setenv("METIS_MODEL", "env-model")

    manifest = load_app_manifest(path)

    assert manifest.name == "Env Agent"
    assert manifest.subtitle == "Custom Harness"
    assert manifest.model == "env-model"
    assert manifest.icon_text == "E"
    assert manifest.allowed_tool_permissions == "read_only"
    assert manifest.state_db_path == ".metis/state.db"


def test_load_app_manifest_uses_state_db_environment_override(monkeypatch, tmp_path):
    path = tmp_path / "metis-agent.json"
    path.write_text(json.dumps({"name": "Agent"}), encoding="utf-8")
    monkeypatch.setenv("METIS_STATE_DB", "custom-state.db")

    manifest = load_app_manifest(path)

    assert manifest.state_db_path == "custom-state.db"


def test_load_app_manifest_accepts_utf8_bom(tmp_path):
    path = tmp_path / "metis-agent.json"
    path.write_text(json.dumps({"name": "BOM Agent"}), encoding="utf-8-sig")

    manifest = load_app_manifest(path)

    assert manifest.name == "BOM Agent"


def test_write_default_app_manifest_creates_rebrandable_manifest(tmp_path):
    path = write_default_app_manifest(tmp_path / "agent.json", name="Acme Analyst", workspace=".")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["name"] == "Acme Analyst"
    assert payload["icon_text"] == "A"
    assert payload["description"] == "Acme Analyst powered by Metis Agent Harness"
