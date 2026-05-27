"""Application manifest for reusable Metis agent shells."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentAppManifest:
    """Branding and runtime defaults shared by CLI, TUI, and Web UI."""

    name: str = "Metis Agent"
    subtitle: str = "Agent Harness"
    description: str = "Domain-neutral agent harness"
    version: str = "0.2.0"
    workspace: str = "."
    model: str = "glm-4.7-flash"
    base_url: str = ""
    profile: str = "small"
    icon_text: str = "M"
    system_prompt_path: str = ""
    developer_prompt_path: str = ""
    allowed_tool_permissions: str = ""
    state_db_path: str = ""
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    # Multi-provider routing configuration
    providers: list[dict[str, Any]] = field(default_factory=list)
    fallback_providers: list[dict[str, Any]] = field(default_factory=list)
    routing_strategy: str = "primary_fallback"
    provider_health_check_interval: float = 60.0
    provider_failover_enabled: bool = True
    hitl_enabled: bool = False
    hitl_auto_approve_read_only: bool = True
    hitl_auto_approve_tools: str = ""
    hitl_auto_deny_tools: str = ""
    hitl_timeout_seconds: float = 300.0
    behavior_rules_enabled: bool = True
    behavior_rules_path: str = ""
    auto_audit_enabled: bool = True
    swarm_audit_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_app_manifest(path: str | Path | None = None, *, workspace: str | Path | None = None) -> AgentAppManifest:
    """Load manifest values from JSON plus environment overrides."""

    data: dict[str, Any] = {}
    manifest_path = Path(path or os.getenv("METIS_APP_MANIFEST", "metis-agent.json"))
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"Metis app manifest root must be an object: {manifest_path}")
        data.update(payload)
    env_overrides = {
        "name": os.getenv("METIS_APP_NAME"),
        "subtitle": os.getenv("METIS_APP_SUBTITLE"),
        "description": os.getenv("METIS_APP_DESCRIPTION"),
        "version": os.getenv("METIS_APP_VERSION"),
        "workspace": str(workspace) if workspace is not None else os.getenv("METIS_WORKSPACE"),
        "model": os.getenv("METIS_MODEL"),
        "base_url": os.getenv("METIS_BASE_URL"),
        "profile": os.getenv("METIS_PROFILE"),
        "icon_text": os.getenv("METIS_APP_ICON"),
        "system_prompt_path": os.getenv("METIS_SYSTEM_PROMPT_PATH"),
        "developer_prompt_path": os.getenv("METIS_DEVELOPER_PROMPT_PATH"),
        "allowed_tool_permissions": os.getenv("METIS_ALLOWED_TOOL_PERMISSIONS"),
        "state_db_path": os.getenv("METIS_STATE_DB"),
        "hitl_enabled": os.getenv("METIS_HITL_ENABLED"),
        "hitl_auto_approve_read_only": os.getenv("METIS_HITL_AUTO_APPROVE_READ_ONLY"),
        "hitl_auto_approve_tools": os.getenv("METIS_HITL_AUTO_APPROVE_TOOLS"),
        "hitl_auto_deny_tools": os.getenv("METIS_HITL_AUTO_DENY_TOOLS"),
        "hitl_timeout_seconds": os.getenv("METIS_HITL_TIMEOUT_SECONDS"),
        "providers": os.getenv("METIS_PROVIDERS"),
        "fallback_providers": os.getenv("METIS_FALLBACK_PROVIDERS"),
        "routing_strategy": os.getenv("METIS_ROUTING_STRATEGY"),
        "provider_health_check_interval": os.getenv("METIS_PROVIDER_HEALTH_CHECK_INTERVAL"),
        "provider_failover_enabled": os.getenv("METIS_PROVIDER_FAILOVER_ENABLED"),
        "behavior_rules_enabled": os.getenv("METIS_BEHAVIOR_RULES_ENABLED"),
        "behavior_rules_path": os.getenv("METIS_BEHAVIOR_RULES_PATH"),
        "auto_audit_enabled": os.getenv("METIS_AUTO_AUDIT_ENABLED"),
        "swarm_audit_enabled": os.getenv("METIS_SWARM_AUDIT_ENABLED"),
    }
    for key, value in env_overrides.items():
        if not value:
            continue
        field_info = AgentAppManifest.__dataclass_fields__.get(key)
        if field_info is not None and field_info.type in ("list[dict[str, Any]]", "list", "dict"):
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        data[key] = parsed
                    else:
                        data[key] = value
                except json.JSONDecodeError:
                    data[key] = value
            else:
                data[key] = value
        else:
            data[key] = value
    if "icon_text" not in data and data.get("name"):
        data["icon_text"] = str(data["name"]).strip()[:1].upper() or "M"
    return AgentAppManifest(**_manifest_fields(data))


def write_default_app_manifest(path: str | Path, *, name: str, workspace: str | Path = ".") -> Path:
    manifest = AgentAppManifest(
        name=name,
        subtitle="Agent Harness",
        description=f"{name} powered by Metis Agent Harness",
        workspace=str(workspace),
        model=os.getenv("METIS_MODEL", "glm-4.7-flash"),
        base_url=os.getenv("METIS_BASE_URL", ""),
        icon_text=name.strip()[:1].upper() or "M",
    )
    path = Path(path)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_app_manifest(manifest: AgentAppManifest, path: str | Path | None = None) -> Path:
    """Write manifest back to JSON file."""
    manifest_path = Path(path or os.getenv("METIS_APP_MANIFEST", "metis-agent.json"))
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _manifest_fields(data: dict[str, Any]) -> dict[str, Any]:
    allowed = set(AgentAppManifest.__dataclass_fields__)
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key not in allowed or value is None:
            continue
        field_info = AgentAppManifest.__dataclass_fields__[key]
        # Preserve list/dict/bool/float types; coerce everything else to str
        if field_info.type in ("list[dict[str, Any]]", "list", "dict"):
            result[key] = value
        elif field_info.type == "bool" or field_info.type is bool:
            result[key] = bool(value) if not isinstance(value, str) else value.lower() in {"true", "1", "yes", "on"}
        elif field_info.type in ("float", "int") or field_info.type is float or field_info.type is int:
            result[key] = value
        else:
            result[key] = str(value)
    return result
