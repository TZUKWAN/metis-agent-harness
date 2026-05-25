"""Stable provenance hashing helpers for eval artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tool_inventory_hash(inventory: dict[str, Any]) -> str:
    tools = []
    for tool in inventory.get("tools", []):
        if not isinstance(tool, dict):
            continue
        tools.append(
            {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "category": tool.get("category", ""),
                "side_effect": tool.get("side_effect", ""),
                "permission_level": tool.get("permission_level", ""),
                "requires_permission": tool.get("requires_permission", False),
                "retry_policy": tool.get("retry_policy", {}),
                "verification": tool.get("verification", {}),
                "metadata": tool.get("metadata", {}),
                "parameters": tool.get("parameters", {}),
            }
        )
    tools.sort(key=lambda item: str(item.get("name", "")))
    return stable_json_hash({"tool_count": len(tools), "tools": tools})


def eval_provenance_payload(
    *,
    suite: str,
    suite_definition_type: str = "",
    schema_version: str = "",
    suite_schema_sha256: str = "",
    task_contract_hash: str = "",
    model: str = "",
    base_url: str = "",
    profile: str = "",
    tool_inventory_hash_value: str = "",
) -> dict[str, str]:
    return {
        "suite": suite,
        "suite_definition_type": suite_definition_type,
        "schema_version": schema_version,
        "suite_schema_sha256": suite_schema_sha256,
        "task_contract_hash": task_contract_hash,
        "model": model,
        "base_url": base_url,
        "profile": profile,
        "tool_inventory_hash": tool_inventory_hash_value,
    }


def eval_provenance_hash(provenance: dict[str, Any]) -> str:
    return stable_json_hash(provenance)
