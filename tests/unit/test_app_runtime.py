from metis.app.manifest import AgentAppManifest
from metis.app.runtime import (
    build_runtime_messages,
    build_runtime_prompt_stack,
    build_runtime_status,
    build_runtime_task_contract,
    manifest_allowed_tool_permissions,
)


def test_build_runtime_messages_loads_manifest_prompt_paths(tmp_path):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "agent-system.md").write_text("System rules for Agent.", encoding="utf-8")
    (prompts / "agent-developer.md").write_text("Developer workflow for Agent.", encoding="utf-8")
    manifest = AgentAppManifest(
        name="Agent",
        workspace=str(tmp_path),
        system_prompt_path="prompts/agent-system.md",
        developer_prompt_path="prompts/agent-developer.md",
    )

    messages = build_runtime_messages("Do work", manifest=manifest)

    assert messages[0]["role"] == "system"
    assert "System rules for Agent." in messages[0]["content"]
    assert "Developer workflow for Agent." in messages[0]["content"]
    assert "Metis task contract v1" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "Do work"}


def test_runtime_task_contract_and_prompt_stack_hashes_are_stable(tmp_path):
    manifest = AgentAppManifest(name="Agent", workspace=str(tmp_path))

    contract = build_runtime_task_contract("Do work", manifest=manifest)
    stack = build_runtime_prompt_stack("Do work", manifest=manifest, task_contract=contract)

    assert contract.contract_hash()
    assert stack.stack_hash()
    assert contract.contract_hash() in stack.to_system_content()


def test_manifest_allowed_tool_permissions_parses_csv():
    manifest = AgentAppManifest(name="Agent", allowed_tool_permissions="read_only, workspace_write")

    assert manifest_allowed_tool_permissions(manifest) == ["read_only", "workspace_write"]


def test_build_runtime_status_exposes_manifest_provider_and_tools(tmp_path):
    manifest = AgentAppManifest(
        name="Agent",
        workspace=str(tmp_path),
        model="glm-4.7-flash",
        allowed_tool_permissions="read_only",
    )

    status = build_runtime_status(manifest)

    assert status["manifest"]["name"] == "Agent"
    assert status["provider_capabilities"]["model"] == "glm-4.7-flash"
    assert status["provider_capabilities"]["native_tool_calling"] is True
    assert status["allowed_tool_permissions"] == ["read_only"]
    assert "read_file" in status["tools"]


def test_build_runtime_status_exposes_state_db_path(tmp_path):
    manifest = AgentAppManifest(name="Agent", workspace=str(tmp_path), state_db_path=".metis/state.db")

    status = build_runtime_status(manifest)

    assert status["state_db_path"].replace("\\", "/").endswith(".metis/state.db")
