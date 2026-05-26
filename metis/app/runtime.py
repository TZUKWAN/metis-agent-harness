"""Shared runtime helpers for user-facing app surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metis.app.manifest import AgentAppManifest
from metis.evidence.ledger import EvidenceLedger
from metis.planning.task_contract import TaskContractV1, build_intake_task_contract
from metis.prompts.assembler import PromptAssembler, PromptParts
from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, AgentRunResult
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


def build_agent_loop(manifest: AgentAppManifest, *, workspace: str | None = None) -> AgentLoop:
    active_workspace = workspace or manifest.workspace
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=active_workspace)
    provider = OpenAICompatibleProvider(model=manifest.model, base_url=manifest.base_url or None)
    state = state_store_for_manifest(manifest, workspace=active_workspace)
    evidence_ledger = EvidenceLedger(state) if state is not None else None
    return AgentLoop(
        provider=provider,
        registry=registry,
        workspace=active_workspace,
        profile=manifest.profile,
        state=state,
        evidence_ledger=evidence_ledger,
    )


def build_runtime_status(manifest: AgentAppManifest, *, workspace: str | None = None) -> dict[str, Any]:
    active_workspace = workspace or manifest.workspace
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=active_workspace)
    provider = OpenAICompatibleProvider(model=manifest.model, base_url=manifest.base_url or None)
    return {
        "manifest": manifest.to_dict(),
        "workspace": active_workspace,
        "profile": manifest.profile,
        "provider_capabilities": provider.capabilities().to_dict(),
        "allowed_tool_permissions": manifest_allowed_tool_permissions(manifest),
        "tools": registry.list_tools(),
        "state_db_path": str(_state_db_path(manifest, workspace=active_workspace)) if manifest.state_db_path else "",
    }


async def run_agent_turn(
    message: str,
    *,
    manifest: AgentAppManifest,
    workspace: str | None = None,
    max_turns: int = 12,
    session_id: str = "default",
    request_id: str = "",
) -> AgentRunResult:
    loop = build_agent_loop(manifest, workspace=workspace)
    task_contract = build_runtime_task_contract(message, manifest=manifest)
    prompt_stack = build_runtime_prompt_stack(message, manifest=manifest, workspace=workspace, task_contract=task_contract)
    return await loop.run(
        AgentRunRequest(
            messages=messages_from_prompt_stack(message, prompt_stack),
            max_turns=max_turns,
            session_id=session_id,
            task_contract_hash=task_contract.contract_hash(),
            prompt_stack_hash=prompt_stack.stack_hash(),
            allowed_tool_permissions=manifest_allowed_tool_permissions(manifest),
            request_id=request_id,
        )
    )


def build_runtime_messages(
    message: str,
    *,
    manifest: AgentAppManifest,
    workspace: str | None = None,
) -> list[dict[str, str]]:
    """Build initial runtime messages from an app manifest and user input."""

    task_contract = build_runtime_task_contract(message, manifest=manifest)
    prompt_stack = build_runtime_prompt_stack(message, manifest=manifest, workspace=workspace, task_contract=task_contract)
    return messages_from_prompt_stack(message, prompt_stack)


def build_runtime_task_contract(
    message: str,
    *,
    manifest: AgentAppManifest,
    allowed_tools: list[str] | None = None,
) -> TaskContractV1:
    return build_intake_task_contract(
        message,
        allowed_tools=allowed_tools,
        source=f"app:{manifest.name}",
    )


def build_runtime_prompt_stack(
    message: str,
    *,
    manifest: AgentAppManifest,
    workspace: str | None = None,
    task_contract: TaskContractV1 | None = None,
):
    active_workspace = workspace or manifest.workspace
    app_system_prompt = _read_prompt(manifest.system_prompt_path, workspace=active_workspace)
    app_developer_prompt = _read_prompt(manifest.developer_prompt_path, workspace=active_workspace)
    contract = task_contract or build_runtime_task_contract(message, manifest=manifest)
    return PromptAssembler().build_stack(
        PromptParts(user_message=message, strict_output=manifest.profile == "small"),
        app_system_prompt=app_system_prompt,
        app_developer_prompt=app_developer_prompt,
        task_contract_v1=contract,
    )


def messages_from_prompt_stack(message: str, prompt_stack) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt_stack.to_system_content()},
        {"role": "user", "content": message},
    ]


def manifest_allowed_tool_permissions(manifest: AgentAppManifest) -> list[str] | None:
    if not manifest.allowed_tool_permissions.strip():
        return None
    return [item.strip() for item in manifest.allowed_tool_permissions.split(",") if item.strip()]


def _read_prompt(prompt_path: str, *, workspace: str) -> str:
    if not prompt_path:
        return ""
    path = Path(prompt_path)
    if not path.is_absolute():
        path = Path(workspace) / path
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def state_store_for_manifest(manifest: AgentAppManifest, *, workspace: str | None = None) -> SQLiteStateStore | None:
    if not manifest.state_db_path.strip():
        return None
    return SQLiteStateStore(_state_db_path(manifest, workspace=workspace or manifest.workspace))


def _state_db_path(manifest: AgentAppManifest, *, workspace: str) -> Path:
    path = Path(manifest.state_db_path)
    if not path.is_absolute():
        path = Path(workspace) / path
    return path
