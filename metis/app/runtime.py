"""Shared runtime helpers for user-facing app surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metis.app.manifest import AgentAppManifest
from metis.events.hooks import HookBus
from metis.evidence.ledger import EvidenceLedger
from metis.planning.task_contract import TaskContractV1, build_intake_task_contract
from metis.prompts.assembler import PromptAssembler, PromptParts
from metis.providers.base import BaseProvider
from metis.providers.factory import build_provider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, AgentRunResult
from metis.state.sqlite_store import SQLiteStateStore
from metis.hitl import build_hitl_approver, register_hitl_hooks
from metis.routing import CapabilityMatchStrategy, ModelRouter, PrimaryFallbackStrategy, ProviderEntry, ProviderHealthMonitor
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


def _parse_mcp_configs(manifest: AgentAppManifest) -> list:
    """Parse MCP server configurations from manifest."""
    from metis.mcp.spec import MCPServerConfig

    configs: list[MCPServerConfig] = []
    for entry in manifest.mcp_servers:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        command = entry.get("command", [])
        if not name or not command:
            continue
        configs.append(
            MCPServerConfig(
                name=name,
                command=command if isinstance(command, list) else [str(command)],
                env=entry.get("env", {}),
                description_prefix=entry.get("description_prefix", ""),
            )
        )
    return configs


async def build_agent_loop_with_mcp(
    manifest: AgentAppManifest,
    *,
    workspace: str | None = None,
    hooks: HookBus | None = None,
    hitl_store: Any = None,
) -> AgentLoop:
    """Build an AgentLoop and connect any configured MCP servers."""
    import logging

    loop = build_agent_loop(manifest, workspace=workspace, hooks=hooks, hitl_store=hitl_store)

    configs = _parse_mcp_configs(manifest)
    if configs:
        from metis.mcp.client import connect_mcp_clients, register_mcp_tools

        clients, errors = await connect_mcp_clients(configs)
        for err in errors:
            logging.getLogger("metis.mcp").warning(err)
        if clients:
            await register_mcp_tools(loop.registry, clients)
            # Store clients on the loop instance for later cleanup
            loop._mcp_clients = clients  # type: ignore[attr-defined]

    return loop


def _build_provider_for_manifest(manifest: AgentAppManifest) -> BaseProvider:
    """Build a single provider or a ModelRouter from manifest config."""
    all_provider_configs = list(manifest.providers)
    # If fallback_providers is set, append with lower priority
    if manifest.fallback_providers:
        for i, cfg in enumerate(manifest.fallback_providers):
            cfg = dict(cfg)
            cfg.setdefault("priority", -1 - i)
            all_provider_configs.append(cfg)

    if not all_provider_configs:
        # Single provider mode (backward compatible)
        return build_provider(model=manifest.model, base_url=manifest.base_url or None)

    entries: list[ProviderEntry] = []
    for cfg in all_provider_configs:
        if not isinstance(cfg, dict):
            continue
        name = cfg.get("name", "") or cfg.get("model", "unnamed")
        model = cfg.get("model", manifest.model)
        base_url = cfg.get("base_url", manifest.base_url or None)
        provider_type = cfg.get("provider_type", "openai_compat")
        priority = cfg.get("priority", 0)
        tags = cfg.get("tags", [])
        cost = cfg.get("cost_per_1k_tokens")
        kwargs = {k: v for k, v in cfg.items() if k not in {"name", "model", "base_url", "provider_type", "priority", "tags", "cost_per_1k_tokens"}}
        provider = build_provider(provider_type=provider_type, model=model, base_url=base_url, **kwargs)
        entries.append(ProviderEntry(name=name, provider=provider, priority=priority, tags=tags or [], cost_per_1k_tokens=cost))

    if len(entries) == 1:
        return entries[0].provider

    strategy: RoutingStrategy
    if manifest.routing_strategy == "capability_match":
        strategy = CapabilityMatchStrategy()
    else:
        strategy = PrimaryFallbackStrategy()

    health_monitor = ProviderHealthMonitor(
        check_interval_seconds=manifest.provider_health_check_interval,
    ) if manifest.provider_failover_enabled else None

    return ModelRouter(
        entries,
        strategy=strategy,
        health_monitor=health_monitor,
        failover_on_error=manifest.provider_failover_enabled,
    )


def build_agent_loop(
    manifest: AgentAppManifest,
    *,
    workspace: str | None = None,
    hooks: HookBus | None = None,
    hitl_store: Any = None,
) -> AgentLoop:
    active_workspace = workspace or manifest.workspace
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=active_workspace)
    provider = _build_provider_for_manifest(manifest)
    state = state_store_for_manifest(manifest, workspace=active_workspace)
    evidence_ledger = EvidenceLedger(state) if state is not None else None
    loop_hooks = hooks or HookBus()
    if manifest.hitl_enabled:
        approver = build_hitl_approver(manifest.to_dict(), store=hitl_store)
        register_hitl_hooks(loop_hooks, approver)
    # Inject behavior-rules hooks if enabled
    if manifest.behavior_rules_enabled:
        from metis.behavior.registry import BehaviorRulesRegistry
        behavior_registry = BehaviorRulesRegistry.from_manifest(manifest.to_dict())
        behavior_registry.register_hooks(loop_hooks)
    return AgentLoop(
        provider=provider,
        registry=registry,
        workspace=active_workspace,
        profile=manifest.profile,
        state=state,
        evidence_ledger=evidence_ledger,
        hooks=loop_hooks,
    )


def build_runtime_status(manifest: AgentAppManifest, *, workspace: str | None = None) -> dict[str, Any]:
    active_workspace = workspace or manifest.workspace
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=active_workspace)
    result: dict[str, Any] = {
        "manifest": manifest.to_dict(),
        "workspace": active_workspace,
        "profile": manifest.profile,
        "allowed_tool_permissions": manifest_allowed_tool_permissions(manifest),
        "tools": registry.list_tools(),
        "state_db_path": str(_state_db_path(manifest, workspace=active_workspace)) if manifest.state_db_path else "",
    }
    try:
        provider = _build_provider_for_manifest(manifest)
        caps = provider.capabilities().to_dict()
        result["provider_capabilities"] = caps
        router_stats = getattr(provider, "get_stats", None)
        if router_stats is not None:
            result["routing_stats"] = router_stats()
    except Exception as exc:
        result["provider_capabilities"] = {"error": str(exc)}
    return result


async def run_agent_turn(
    message: str,
    *,
    manifest: AgentAppManifest,
    workspace: str | None = None,
    max_turns: int = 12,
    session_id: str = "default",
    request_id: str = "",
    hooks: HookBus | None = None,
    hitl_store: Any = None,
) -> AgentRunResult:
    loop = await build_agent_loop_with_mcp(manifest, workspace=workspace, hooks=hooks, hitl_store=hitl_store)
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
    behavior_rules_prompt = ""
    if manifest.behavior_rules_enabled:
        from metis.behavior.registry import BehaviorRulesRegistry
        behavior_registry = BehaviorRulesRegistry.from_manifest(manifest.to_dict())
        behavior_rules_prompt = behavior_registry.get_prompt_content()
    return PromptAssembler().build_stack(
        PromptParts(user_message=message, strict_output=manifest.profile == "small"),
        app_system_prompt=app_system_prompt,
        app_developer_prompt=app_developer_prompt,
        task_contract_v1=contract,
        behavior_rules_prompt=behavior_rules_prompt,
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
